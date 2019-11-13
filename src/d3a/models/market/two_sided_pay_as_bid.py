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

from d3a.models.market.one_sided import OneSidedMarket
from d3a.d3a_core.exceptions import BidNotFound, InvalidBid, InvalidTrade
from d3a.models.market.market_structures import Bid, Trade, TradeBidInfo
from d3a.events.event_structures import MarketEvent
from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a.models.market.grid_fees.base_model import GridFees

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
        return GridFees.update_incoming_bid_with_fee(bid_price, original_bid_price)

    def bid(self, price: float, energy: float, buyer: str, seller: str,
            bid_id: str = None, original_bid_price=None, buyer_origin=None) -> Bid:
        if energy <= 0:
            raise InvalidBid()

        self._update_new_bid_price_with_fee(price, original_bid_price)
        bid = Bid(str(uuid.uuid4()) if bid_id is None else bid_id,
                  price, energy, buyer, seller, original_bid_price, buyer_origin)
        self.bids[bid.id] = bid
        self.bid_history.append(bid)
        log.debug(f"[BID][NEW][{self.time_slot_str}] {bid}")
        return bid

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
        residual = None

        if energy <= 0:
            raise InvalidTrade("Energy cannot be negative or zero.")
        elif energy > market_bid.energy:
            raise InvalidTrade("Traded energy cannot be more than the bid energy.")
        elif energy < market_bid.energy:
            # Partial bidding
            energy_portion = energy / market_bid.energy
            residual_price = (1 - energy_portion) * market_bid.price
            residual_energy = market_bid.energy - energy

            # Manually creating the bid in order to not double-charge the fee of the
            # residual bid
            changed_bid = Bid(
                str(uuid.uuid4()), residual_price, residual_energy,
                buyer, seller,
                original_bid_price=(1 - energy_portion) * orig_price,
                buyer_origin=market_bid.buyer_origin
            )

            self.bids[changed_bid.id] = changed_bid
            self.bid_history.append(changed_bid)

            self._notify_listeners(MarketEvent.BID_CHANGED,
                                   existing_bid=bid, new_bid=changed_bid)
            residual = changed_bid

            revenue, fees, final_trade_rate = GridFees.calculate_trade_price_and_fees(
                trade_offer_info, self.transfer_fee_ratio
            )
            self.market_fee += fees
            final_price = energy * final_trade_rate
            bid = Bid(bid.id, final_price, energy, buyer, seller,
                      original_bid_price=energy_portion * orig_price,
                      buyer_origin=bid.buyer_origin)
        else:
            revenue, fees, final_trade_rate = GridFees.calculate_trade_price_and_fees(
                trade_offer_info, self.transfer_fee_ratio
            )
            self.market_fee += fees
            final_price = energy * final_trade_rate
            bid = bid._replace(price=final_price)

        trade = Trade(str(uuid.uuid4()), self.now, bid, seller,
                      buyer, residual, already_tracked=already_tracked,
                      offer_bid_trade_info=GridFees.propagate_original_offer_info_on_bid_trade(
                          trade_offer_info, self.transfer_fee_ratio),
                      buyer_origin=bid.buyer_origin, seller_origin=seller_origin
                      )

        if already_tracked is False:
            self._update_stats_after_trade(trade, bid, bid.buyer, already_tracked)
            log.info(f"[TRADE][BID] [{self.time_slot_str}] {trade}")
            final_bid = bid._replace(price=final_price)
            trade = trade._replace(offer=final_bid)

        self._notify_listeners(MarketEvent.BID_TRADED, bid_trade=trade)
        if not trade.residual:
            self._notify_listeners(MarketEvent.BID_DELETED, bid=market_bid)
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
        for offer in sorted_offers:
            for bid in sorted_bids:
                if bid.id not in already_selected_bids and \
                        (offer.price / offer.energy - bid.price / bid.energy) <= \
                        FLOATING_POINT_TOLERANCE and offer.seller != bid.buyer:
                    already_selected_bids.add(bid.id)
                    yield bid, offer
                    break

    def match_offers_bids(self):
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
            self.accept_offer(offer_or_id=offer,
                              buyer=bid.buyer,
                              energy=selected_energy,
                              trade_rate=matched_rate,
                              already_tracked=False,
                              trade_bid_info=trade_bid_info,
                              buyer_origin=bid.buyer_origin)
            self.accept_bid(bid=bid,
                            energy=selected_energy,
                            seller=offer.seller,
                            buyer=bid.buyer,
                            already_tracked=True,
                            trade_rate=matched_rate,
                            trade_offer_info=trade_bid_info,
                            seller_origin=offer.seller_origin)
