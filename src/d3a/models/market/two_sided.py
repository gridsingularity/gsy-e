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
import itertools
import uuid
from dataclasses import replace
from logging import getLogger
from math import isclose
from typing import Dict, List, Union  # noqa

from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a.d3a_core.exceptions import (BidNotFoundException, InvalidBid,
                                     InvalidBidOfferPairException, InvalidTrade, MarketException)
from d3a.d3a_core.util import short_offer_bid_log_str
from d3a.events.event_structures import MarketEvent
from d3a.models.market import lock_market_action
from d3a.models.market.market_structures import Bid, Offer, Trade, TradeBidOfferInfo
from d3a.models.market.market_validators import RequirementsSatisfiedChecker
from d3a.models.market.one_sided import OneSidedMarket
from d3a_interface.constants_limits import ConstSettings
from d3a_interface.dataclasses import BidOfferMatch

log = getLogger(__name__)


class TwoSidedMarket(OneSidedMarket):
    """Extends One sided market class and adds support for bidding functionality.

    A market type that allows producers to place energy offers to the markets
    (exactly the same way as on the one-sided market case), but also allows the consumers
    to place energy bids on their respective markets.
    Contrary to the one sided market, where the offers are selected directly by the consumers,
    the offers and bids are being matched via some matching algorithm.
    """

    def __init__(self, time_slot=None, bc=None, notification_listener=None, readonly=False,
                 grid_fee_type=ConstSettings.IAASettings.GRID_FEE_TYPE,
                 grid_fees=None, name=None, in_sim_duration=True):
        super().__init__(time_slot, bc, notification_listener, readonly, grid_fee_type,
                         grid_fees, name, in_sim_duration=in_sim_duration)

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

    def _update_new_bid_price_with_fee(self, bid_price, original_bid_price):
        return self.fee_class.update_incoming_bid_with_fee(bid_price, original_bid_price)

    @lock_market_action
    def get_bids(self):
        return self.bids

    @lock_market_action
    def bid(self, price: float, energy: float, buyer: str, buyer_origin: str,
            bid_id: str = None, original_bid_price=None, adapt_price_with_fees=True,
            add_to_history=True, buyer_origin_id=None, buyer_id=None,
            attributes: Dict = None, requirements: List[Dict] = None) -> Bid:
        if energy <= 0:
            raise InvalidBid()

        if original_bid_price is None:
            original_bid_price = price

        if adapt_price_with_fees:
            price = self._update_new_bid_price_with_fee(price, original_bid_price)

        if price < 0.0:
            raise MarketException("Negative price after taxes, bid cannot be posted.")

        bid = Bid(str(uuid.uuid4()) if bid_id is None else bid_id,
                  self.now, price, energy, buyer, original_bid_price, buyer_origin,
                  buyer_origin_id=buyer_origin_id, buyer_id=buyer_id,
                  attributes=attributes, requirements=requirements)

        self.bids[bid.id] = bid
        if add_to_history is True:
            self.bid_history.append(bid)
        log.debug(f"[BID][NEW][{self.time_slot_str}] {bid}")
        return bid

    @lock_market_action
    def delete_bid(self, bid_or_id: Union[str, Bid]):
        if isinstance(bid_or_id, Bid):
            bid_or_id = bid_or_id.id
        bid = self.bids.pop(bid_or_id, None)
        if not bid:
            raise BidNotFoundException(bid_or_id)
        log.debug(f"[BID][DEL][{self.time_slot_str}] {bid}")
        self._notify_listeners(MarketEvent.BID_DELETED, bid=bid)

    def split_bid(self, original_bid, energy, orig_bid_price):

        self.bids.pop(original_bid.id, None)
        # same bid id is used for the new accepted_bid
        original_accepted_price = energy / original_bid.energy * orig_bid_price
        accepted_bid = self.bid(bid_id=original_bid.id,
                                price=original_bid.price * (energy / original_bid.energy),
                                energy=energy,
                                buyer=original_bid.buyer,
                                original_bid_price=original_accepted_price,
                                buyer_origin=original_bid.buyer_origin,
                                buyer_origin_id=original_bid.buyer_origin_id,
                                buyer_id=original_bid.buyer_id,
                                adapt_price_with_fees=False,
                                add_to_history=False,
                                attributes=original_bid.attributes,
                                requirements=original_bid.requirements)

        residual_price = (1 - energy / original_bid.energy) * original_bid.price
        residual_energy = original_bid.energy - energy

        original_residual_price = \
            ((original_bid.energy - energy) / original_bid.energy) * orig_bid_price

        residual_bid = self.bid(price=residual_price,
                                energy=residual_energy,
                                buyer=original_bid.buyer,
                                original_bid_price=original_residual_price,
                                buyer_origin=original_bid.buyer_origin,
                                buyer_origin_id=original_bid.buyer_origin_id,
                                buyer_id=original_bid.buyer_id,
                                adapt_price_with_fees=False,
                                add_to_history=True,
                                attributes=original_bid.attributes,
                                requirements=original_bid.requirements)

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
        revenue, grid_fee_rate, final_trade_rate = \
            self.fee_class.calculate_trade_price_and_fees(trade_offer_info)
        return grid_fee_rate * energy, energy * final_trade_rate

    @lock_market_action
    def accept_bid(self, bid: Bid, energy: float = None,
                   seller: str = None, buyer: str = None, already_tracked: bool = False,
                   trade_rate: float = None, trade_offer_info=None, seller_origin=None,
                   seller_origin_id=None, seller_id=None):
        market_bid = self.bids.pop(bid.id, None)
        if market_bid is None:
            raise BidNotFoundException("During accept bid: " + str(bid))

        buyer = market_bid.buyer if buyer is None else buyer

        if energy is None or isclose(energy, market_bid.energy, abs_tol=1e-8):
            energy = market_bid.energy

        orig_price = bid.original_bid_price if bid.original_bid_price is not None else bid.price
        residual_bid = None

        if energy <= 0:
            raise InvalidTrade("Energy cannot be negative or zero.")
        elif energy > market_bid.energy:
            raise InvalidTrade(f"Traded energy ({energy}) cannot be more than the "
                               f"bid energy ({market_bid.energy}).")
        elif energy < market_bid.energy:
            # partial bid trade
            accepted_bid, residual_bid = self.split_bid(market_bid, energy, orig_price)
            bid = accepted_bid

            # Delete the accepted bid from self.bids:
            try:
                self.bids.pop(accepted_bid.id)
            except KeyError:
                raise BidNotFoundException(
                    f"Bid {accepted_bid.id} not found in self.bids ({self.name}).")
        else:
            # full bid trade, nothing further to do here
            pass

        fee_price, trade_price = self.determine_bid_price(trade_offer_info, energy)
        bid = replace(bid, price=trade_price)

        # Do not adapt grid fees when creating the bid_trade_info structure, to mimic
        # the behavior of the forwarded bids which use the source market fee.
        updated_bid_trade_info = self.fee_class.propagate_original_offer_info_on_bid_trade(
            trade_offer_info, ignore_fees=True
        )

        trade = Trade(str(uuid.uuid4()), self.now, bid, seller,
                      buyer, residual_bid, already_tracked=already_tracked,
                      offer_bid_trade_info=updated_bid_trade_info,
                      buyer_origin=bid.buyer_origin, seller_origin=seller_origin,
                      fee_price=fee_price, seller_origin_id=seller_origin_id,
                      buyer_origin_id=bid.buyer_origin_id, seller_id=seller_id,
                      buyer_id=bid.buyer_id
                      )

        if already_tracked is False:
            self._update_stats_after_trade(trade, bid, already_tracked)
            log.info(f"[TRADE][BID] [{self.name}] [{self.time_slot_str}] {trade}")

        self._notify_listeners(MarketEvent.BID_TRADED, bid_trade=trade)
        return trade

    def accept_bid_offer_pair(self, bid, offer, clearing_rate, trade_bid_info, selected_energy):
        already_tracked = bid.buyer == offer.seller
        trade = self.accept_offer(offer_or_id=offer,
                                  buyer=bid.buyer,
                                  energy=selected_energy,
                                  trade_rate=clearing_rate,
                                  already_tracked=already_tracked,
                                  trade_bid_info=trade_bid_info,
                                  buyer_origin=bid.buyer_origin,
                                  buyer_origin_id=bid.buyer_origin_id,
                                  buyer_id=bid.buyer_id)

        bid_trade = self.accept_bid(bid=bid,
                                    energy=selected_energy,
                                    seller=offer.seller,
                                    buyer=bid.buyer,
                                    already_tracked=True,
                                    trade_rate=clearing_rate,
                                    trade_offer_info=trade_bid_info,
                                    seller_origin=offer.seller_origin,
                                    seller_origin_id=offer.seller_origin_id,
                                    seller_id=offer.seller_id)
        return bid_trade, trade

    def match_recommendations(
            self, recommendations: List[BidOfferMatch.serializable_dict]) -> None:
        """Match a list of bid/offer pairs, create trades and residual offers/bids."""

        while recommendations:
            recommended_pair = recommendations.pop(0)
            recommended_pair = BidOfferMatch.from_dict(recommended_pair)
            selected_energy = recommended_pair.selected_energy
            clearing_rate = recommended_pair.trade_rate
            market_offers = [
                self.offers.get(offer["id"]) for offer in recommended_pair.offers]
            market_bids = [self.bids.get(bid["id"]) for bid in recommended_pair.bids]

            if not all(market_offers):
                # If not all received offers exist in the market, skip the current recommendation
                continue
            if not all(market_bids):
                # If not all received bids exist in the market, skip the current recommendation
                continue

            self.validate_bid_offer_match(
                market_bids, market_offers,
                clearing_rate, selected_energy)

            market_offers = iter(market_offers)
            market_bids = iter(market_bids)
            market_offer = next(market_offers)
            market_bid = next(market_bids)
            while True:
                original_bid_rate = market_bid.original_bid_price / market_bid.energy
                trade_bid_info = TradeBidOfferInfo(
                    original_bid_rate=original_bid_rate,
                    propagated_bid_rate=market_bid.energy_rate,
                    original_offer_rate=market_offer.original_offer_price / market_offer.energy,
                    propagated_offer_rate=market_offer.energy_rate,
                    trade_rate=original_bid_rate)

                bid_trade, offer_trade = self.accept_bid_offer_pair(
                    market_bid, market_offer, clearing_rate,
                    trade_bid_info, min(selected_energy, market_offer.energy, market_bid.energy))
                if offer_trade.residual:
                    market_offer = offer_trade.residual
                else:
                    market_offer = next(market_offers, None)
                if bid_trade.residual:
                    market_bid = bid_trade.residual
                else:
                    market_bid = next(market_bids, None)
                recommendations = (
                    self._replace_offers_bids_with_residual_in_recommendations_list(
                        recommendations, offer_trade, bid_trade)
                )
                if not (market_bid and market_offer):
                    # If we reach the end of the offers/bids lists, break
                    break

    @staticmethod
    def _validate_requirements_satisfied(
            bid: Bid, offer: Offer, clearing_rate: float = None,
            selected_energy: float = None) -> None:
        """Validate if both trade parties satisfy each other's requirements.

        :raises:
            InvalidBidOfferPairException: Bid offer pair failed the validation
        """
        if ((offer.requirements or bid.requirements) and
                not RequirementsSatisfiedChecker.is_satisfied(
                    offer=offer, bid=bid, clearing_rate=clearing_rate,
                    selected_energy=selected_energy)):
            # If no requirement dict is satisfied
            raise InvalidBidOfferPairException(
                f"OFFER: {offer} & BID: {bid} requirements failed the validation.")

    @classmethod
    def validate_bid_offer_match(
            cls, bids: List[Bid], offers: List[Offer],
            clearing_rate: float, selected_energy: float) -> None:
        """Basic validation function for bids against offers.

        Raises:
            InvalidBidOfferPairException: Bid offer pair failed the validation
        """
        bids_total_energy = sum([bid.energy for bid in bids])
        offers_total_energy = sum([offer.energy for offer in offers])
        # All combinations of bids and offers [(bid, offer), (bid, offer)...]
        # Example List1: [A, B], List2: [C, D] -> combinations: [(A, C), (A, D), (B, C), (B, D)]
        bids_offers_combinations = itertools.product(bids, offers)
        if not (
                bids_total_energy >= selected_energy and
                offers_total_energy >= selected_energy
                and all(
                    (bid.energy_rate + FLOATING_POINT_TOLERANCE) >= clearing_rate for bid in bids)
                and all(
                    (offer.energy_rate <= clearing_rate + FLOATING_POINT_TOLERANCE
                        for offer in offers))):
            raise InvalidBidOfferPairException
        for combination in bids_offers_combinations:
            cls._validate_requirements_satisfied(
                bid=combination[0], offer=combination[1], clearing_rate=clearing_rate,
                selected_energy=selected_energy)

    @classmethod
    def _replace_offers_bids_with_residual_in_recommendations_list(
            cls, recommendations: List[Dict], offer_trade: Trade, bid_trade: Trade
    ) -> List[BidOfferMatch.serializable_dict]:
        """
        If a trade resulted in a residual offer/bid, upcoming matching list with same offer/bid
        needs to be replaced with residual offer/bid.
        :param recommendations: Recommended list of offer/bid matches
        :param offer_trade: Trade info of the successful offer
        :param bid_trade: Trade info of the successful bid
        :return: The updated matching offer/bid pair list with existing offer/bid
        replaced with corresponding residual offer/bid
        """

        def replace_recommendations_with_residuals(recommendation: Dict):
            for index, offer in enumerate(recommendation["offers"]):
                if offer["id"] == offer_trade.offer.id:
                    recommendation["offers"][index] = offer_trade.residual.serializable_dict()
            for index, bid in enumerate(recommendation["bids"]):
                if bid["id"] == bid_trade.offer.id:
                    recommendation["bids"][index] = bid_trade.residual.serializable_dict()
            return recommendation

        if offer_trade.residual or bid_trade.residual:
            recommendations = [replace_recommendations_with_residuals(recommendation)
                               for recommendation in recommendations]
        return recommendations
