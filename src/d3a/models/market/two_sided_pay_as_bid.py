"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import uuid
from typing import Union  # noqa
from logging import getLogger

from d3a.models.market import lock_market_action
from d3a.models.market.one_sided import OneSidedMarket
from d3a.d3a_core.exceptions import BidNotFound, InvalidBid, InvalidTrade
from d3a.models.market.market_structures import Bid, Trade, TradeBidInfo
from d3a.events.event_structures import MarketEvent
from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a.models.market.grid_fees.base_model import GridFees
from d3a.d3a_core.util import short_offer_bid_log_str

log = getLogger(__name__)


class TwoSidedPayAsBid(OneSidedMarket):

    def __init__(self, time_slot=None, bc=None, notification_listener=None, readonly=False,
                 transfer_fees=None, name=None):
        super().__init__(time_slot, bc, notification_listener, readonly, transfer_fees, name)

    def __repr__(self):  # pragma: no cover
        return "<TwoSidedPayAsBid{} bids: {} (E: {} kWh V:{}) " \
               "offers: {} (E: {} kWh V: {}) trades: {} (E: {} kWh, V: {})>"\
            .format(" {}".format(self.time_slot_str),
                    len(self.bids),
                    sum(b.energy for b in self.bids.values()),
                    sum(b.price for b in self.bids.values()),
                    len(self.offers),
                    sum(o.energy for o in self.offers.values()),
                    sum(o.price for o in self.offers.values()),
                    len(self.trades),
                    self.accumulated_trade_energy,
                    self.accumulated_trade_price
                    )

    def _update_new_offer_price_with_fee(self, offer_price, original_offer_price, energy):
        """
        Override one sided market private method to abstract away the grid fee calculation
        when placing an offer to a market.
        :param offer_price: Price of the offer coming from the source market, in cents
        :param original_offer_price: Price of the original offer from the device
        :param energy: Not required here, added to comply with the one-sided market implementation
        :return: Updated price for the forwarded offer on this market
        """
        return GridFees.update_incoming_offer_with_fee(
            offer_price, original_offer_price, self.transfer_fee_ratio
        )

    def _update_new_bid_price_with_fee(self, bid_price, original_bid_price):
        return GridFees.update_incoming_bid_with_fee(bid_price, original_bid_price,
                                                     self.transfer_fee_ratio)

    @lock_market_action
    def bid(self, price: float, energy: float, buyer: str, seller: str,
            bid_id: str = None, original_bid_price=None, buyer_origin=None,
            adapt_price_with_fees=True) -> Bid:
        if energy <= 0:
            raise InvalidBid()

        if original_bid_price is None:
            original_bid_price = price

        if adapt_price_with_fees:
            price = self._update_new_bid_price_with_fee(price, original_bid_price)

        bid = Bid(str(uuid.uuid4()) if bid_id is None else bid_id,
                  price, energy, buyer, seller, original_bid_price, buyer_origin)
        self.bids[bid.id] = bid
        self.bid_history.append(bid)
        log.debug(f"[BID][NEW][{self.time_slot_str}] {bid}")
        return bid

    @lock_market_action
    def delete_bid(self, bid_or_id: Union[str, Bid]):
        if isinstance(bid_or_id, Bid):
            bid_or_id = bid_or_id.id
        bid = self.bids.pop(bid_or_id, None)
        if not bid:
            raise BidNotFound(bid_or_id)
        log.debug(f"[BID][DEL][{self.time_slot_str}] {bid}")
        self._notify_listeners(MarketEvent.BID_DELETED, bid=bid)

    def _update_bid_fee_and_calculate_final_price(self, energy, trade_rate,
                                                  energy_portion, original_price):
        fees = self.transfer_fee_ratio * original_price * energy_portion \
            + self.transfer_fee_const * energy
        self.market_fee += fees
        return energy * trade_rate + fees

    def split_bid(self, original_bid, energy, orig_bid_price):

        self.bids.pop(original_bid.id, None)
        # same bid id is used for the new accepted_bid
        original_accepted_price = energy / original_bid.energy * orig_bid_price
        accepted_bid = self.bid(bid_id=original_bid.id,
                                price=original_bid.price * (energy / original_bid.energy),
                                energy=energy,
                                buyer=original_bid.buyer,
                                seller=original_bid.seller,
                                original_bid_price=original_accepted_price,
                                buyer_origin=original_bid.buyer_origin,
                                adapt_price_with_fees=False)

        residual_price = (1 - energy / original_bid.energy) * original_bid.price
        residual_energy = original_bid.energy - energy

        original_residual_price = \
            ((original_bid.energy - energy) / original_bid.energy) * orig_bid_price

        residual_bid = self.bid(price=residual_price,
                                energy=residual_energy,
                                buyer=original_bid.buyer,
                                seller=original_bid.seller,
                                original_bid_price=original_residual_price,
                                buyer_origin=original_bid.buyer_origin,
                                adapt_price_with_fees=False)

        log.debug(f"[BID][SPLIT][{self.time_slot_str}, {self.name}] "
                  f"({short_offer_bid_log_str(original_bid)} into "
                  f"{short_offer_bid_log_str(accepted_bid)} and "
                  f"{short_offer_bid_log_str(residual_bid)}")

        self._notify_listeners(MarketEvent.BID_SPLIT,
                               original_bid=original_bid,
                               accepted_bid=accepted_bid,
                               residual_bid=residual_bid)

        return accepted_bid, residual_bid

    def determine_bid_price(self, trade_offer_info, energy):
        revenue, grid_fee_rate, final_trade_rate = GridFees.calculate_trade_price_and_fees(
            trade_offer_info, self.transfer_fee_ratio
        )
        self.market_fee += grid_fee_rate * energy
        return grid_fee_rate, energy * final_trade_rate

    @lock_market_action
    def accept_bid(self, bid: Bid, energy: float = None,
                   seller: str = None, buyer: str = None, already_tracked: bool = False,
                   trade_rate: float = None, trade_offer_info=None, seller_origin=None):
        market_bid = self.bids.pop(bid.id, None)
        if market_bid is None:
            raise BidNotFound("During accept bid: " + str(bid))

        seller = market_bid.seller if seller is None else seller
        buyer = market_bid.buyer if buyer is None else buyer
        energy = market_bid.energy if energy is None else energy
        if trade_rate is None:
            trade_rate = market_bid.price / market_bid.energy

        assert trade_rate <= (market_bid.price / market_bid.energy) + FLOATING_POINT_TOLERANCE, \
            f"trade rate: {trade_rate} market {market_bid.price / market_bid.energy}"

        orig_price = bid.original_bid_price if bid.original_bid_price is not None else bid.price
        residual_bid = None

        if energy <= 0:
            raise InvalidTrade("Energy cannot be negative or zero.")
        elif energy > market_bid.energy:
            raise InvalidTrade("Traded energy cannot be more than the bid energy.")
        elif energy < market_bid.energy:
            # partial bid trade
            accepted_bid, residual_bid = self.split_bid(market_bid, energy, orig_price)
            bid = accepted_bid

            # Delete the accepted bid from self.bids:
            try:
                self.bids.pop(accepted_bid.id)
            except KeyError:
                raise BidNotFound(f"Bid {accepted_bid.id} not found in self.bids ({self.name}).")
        else:
            # full bid trade, nothing further to do here
            pass

        grid_fee_rate, trade_price = self.determine_bid_price(trade_offer_info, energy)
        bid = bid._replace(price=trade_price)

        # Do not adapt grid fees when creating the bid_trade_info structure, to mimic
        # the behavior of the forwarded bids which use the source market fee.
        updated_bid_trade_info = GridFees.propagate_original_offer_info_on_bid_trade(
                          trade_offer_info, 0.0)
        fee_price = grid_fee_rate * bid.energy

        trade = Trade(str(uuid.uuid4()), self.now, bid, seller,
                      buyer, residual_bid, already_tracked=already_tracked,
                      offer_bid_trade_info=updated_bid_trade_info,
                      buyer_origin=bid.buyer_origin, seller_origin=seller_origin,
                      fee_price=fee_price
                      )

        if already_tracked is False:
            self._update_stats_after_trade(trade, bid, bid.buyer, already_tracked)
            log.info(f"[TRADE][BID] [{self.time_slot_str}] {trade}")

        self._notify_listeners(MarketEvent.BID_TRADED, bid_trade=trade)
        return trade

    def _perform_pay_as_bid_matching(self):
        # Pay as bid first
        # There are 2 simplistic approaches to the problem
        # 1. Match the cheapest offer with the most expensive bid. This will favor the sellers
        # 2. Match the cheapest offer with the cheapest bid. This will favor the buyers,
        #    since the most affordable offers will be allocated for the most aggressive buyers.

        # Sorted bids in descending order
        sorted_bids = self.sorting(self.bids, True)

        # Sorted offers in descending order
        sorted_offers = self.sorting(self.offers, True)

        already_selected_bids = set()
        offer_bid_pairs = []
        for offer in sorted_offers:
            for bid in sorted_bids:
                if bid.id not in already_selected_bids and \
                        (offer.price / offer.energy - bid.price / bid.energy) <= \
                        FLOATING_POINT_TOLERANCE and offer.seller != bid.buyer:
                    already_selected_bids.add(bid.id)
                    offer_bid_pairs.append(tuple((bid, offer)))
                    break
        return offer_bid_pairs

    def accept_bid_offer_pair(self, bid, offer, clearing_rate, trade_bid_info, selected_energy):
        already_tracked = bid.buyer == offer.seller
        trade = self.accept_offer(offer_or_id=offer,
                                  buyer=bid.buyer,
                                  energy=selected_energy,
                                  trade_rate=clearing_rate,
                                  already_tracked=already_tracked,
                                  trade_bid_info=trade_bid_info,
                                  buyer_origin=bid.buyer_origin)

        bid_trade = self.accept_bid(bid=bid,
                                    energy=selected_energy,
                                    seller=offer.seller,
                                    buyer=bid.buyer,
                                    already_tracked=True,
                                    trade_rate=clearing_rate,
                                    trade_offer_info=trade_bid_info,
                                    seller_origin=offer.seller_origin)
        return bid_trade, trade

    def match_offers_bids(self):
        while len(self._perform_pay_as_bid_matching()) > 0:
            for bid, offer in self._perform_pay_as_bid_matching():
                selected_energy = bid.energy if bid.energy < offer.energy else offer.energy
                original_bid_rate = bid.original_bid_price / bid.energy
                matched_rate = bid.price / bid.energy

                trade_bid_info = TradeBidInfo(
                    original_bid_rate=original_bid_rate,
                    propagated_bid_rate=bid.price/bid.energy,
                    original_offer_rate=offer.original_offer_price/offer.energy,
                    propagated_offer_rate=offer.price/offer.energy,
                    trade_rate=original_bid_rate)

                self.accept_bid_offer_pair(bid, offer, matched_rate,
                                           trade_bid_info, selected_energy)
