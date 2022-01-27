"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
from copy import deepcopy
from logging import getLogger
from math import isclose
from typing import Dict, List, Union, Tuple, Optional

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import Bid, Offer, Trade, TradeBidOfferInfo, BidOfferMatch
from gsy_framework.matching_algorithms.requirements_validators import RequirementsSatisfiedChecker
from pendulum import DateTime

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.gsy_e_core.exceptions import (
    BidNotFoundException, InvalidBid, InvalidBidOfferPairException, InvalidTrade, MarketException)
from gsy_e.gsy_e_core.util import short_offer_bid_log_str, is_external_matching_enabled
from gsy_e.events.event_structures import MarketEvent
from gsy_e.models.market import lock_market_action
from gsy_e.models.market.one_sided import OneSidedMarket

log = getLogger(__name__)


class TwoSidedMarket(OneSidedMarket):
    """Extend One sided market class and add support for bidding functionality.

    A market type that allows producers to place energy offers to the markets
    (exactly the same way as on the one-sided market case), but also allows the consumers
    to place energy bids on their respective markets.
    Contrary to the one sided market, where the offers are selected directly by the consumers,
    the offers and bids are being matched via some matching algorithm.
    """

    def __init__(self, time_slot=None, bc=None, notification_listener=None, readonly=False,
                 grid_fee_type=ConstSettings.MASettings.GRID_FEE_TYPE,
                 grid_fees=None, name=None, in_sim_duration=True):
        super().__init__(time_slot, bc, notification_listener, readonly, grid_fee_type,
                         grid_fees, name, in_sim_duration=in_sim_duration)

    @property
    def _debug_log_market_type_identifier(self):
        return "[TWO_SIDED]"

    def __repr__(self):
        return (f"<{self._class_name} {self.time_slot_str} bids: {len(self.bids)}"
                f" (E: {sum(b.energy for b in self.bids.values())} kWh"
                f" V:{sum(b.price for b in self.bids.values())}) "
                f"offers: {len(self.offers)} (E: {sum(o.energy for o in self.offers.values())} kWh"
                f" V: {sum(o.price for o in self.offers.values())}) "
                f"trades: {len(self.trades)} (E: {self.accumulated_trade_energy} kWh"
                f", V: {self.accumulated_trade_price})>")

    def _update_new_bid_price_with_fee(self, price, original_price):
        return self.fee_class.update_incoming_bid_with_fee(price, original_price)

    @lock_market_action
    def get_bids(self) -> Dict:
        """
        Retrieves a copy of all open bids of the market. The copy of the bids guarantees
        that the return dict will remain unaffected from any mutations of the market bid list
        that might happen concurrently (more specifically can be used in for loops without raising
        the 'dict changed size during iteration' exception)
        Returns: dict with open bids, bid id as keys, and Bid objects as values

        """
        return deepcopy(self.bids)

    @lock_market_action
    def bid(self, price: float, energy: float, buyer: str, buyer_origin: str,
            bid_id: Optional[str] = None,
            original_price: Optional[float] = None,
            adapt_price_with_fees: bool = True,
            add_to_history: bool = True,
            buyer_origin_id: Optional[str] = None,
            buyer_id: Optional[str] = None,
            attributes: Optional[Dict] = None,
            requirements: Optional[List[Dict]] = None,
            time_slot: Optional[DateTime] = None) -> Bid:
        if energy <= 0:
            raise InvalidBid()

        if not time_slot:
            time_slot = self.time_slot

        if original_price is None:
            original_price = price

        if adapt_price_with_fees:
            price = self._update_new_bid_price_with_fee(price, original_price)

        if price < 0.0:
            raise MarketException("Negative price after taxes, bid cannot be posted.")

        bid = Bid(str(uuid.uuid4()) if bid_id is None else bid_id,
                  self.now, price, energy, buyer, original_price, buyer_origin,
                  buyer_origin_id=buyer_origin_id, buyer_id=buyer_id,
                  attributes=attributes, requirements=requirements, time_slot=time_slot)

        self.bids[bid.id] = bid
        if add_to_history is True:
            self.bid_history.append(bid)
        log.debug("%s[BID][NEW][%s] %s", self._debug_log_market_type_identifier,
                  self.time_slot_str, bid)
        return bid

    @lock_market_action
    def delete_bid(self, bid_or_id: Union[str, Bid]):
        if isinstance(bid_or_id, Bid):
            bid_or_id = bid_or_id.id
        bid = self.bids.pop(bid_or_id, None)
        if not bid:
            raise BidNotFoundException(bid_or_id)
        log.debug("%s[BID][DEL][%s] %s",
                  self._debug_log_market_type_identifier, self.time_slot_str, bid)
        self._notify_listeners(MarketEvent.BID_DELETED, bid=bid)

    def split_bid(self, original_bid: Bid, energy: float, orig_bid_price: float):
        """Split bit into two, one with provided energy, the other with the residual."""

        self.bids.pop(original_bid.id, None)

        # same bid id is used for the new accepted_bid
        original_accepted_price = energy / original_bid.energy * orig_bid_price
        accepted_bid = self.bid(bid_id=original_bid.id,
                                price=original_bid.price * (energy / original_bid.energy),
                                energy=energy,
                                buyer=original_bid.buyer,
                                original_price=original_accepted_price,
                                buyer_origin=original_bid.buyer_origin,
                                buyer_origin_id=original_bid.buyer_origin_id,
                                buyer_id=original_bid.buyer_id,
                                adapt_price_with_fees=False,
                                add_to_history=False,
                                attributes=original_bid.attributes,
                                requirements=original_bid.requirements,
                                time_slot=original_bid.time_slot)

        residual_price = (1 - energy / original_bid.energy) * original_bid.price
        residual_energy = original_bid.energy - energy

        original_residual_price = ((original_bid.energy - energy) /
                                   original_bid.energy) * orig_bid_price

        residual_bid = self.bid(price=residual_price,
                                energy=residual_energy,
                                buyer=original_bid.buyer,
                                original_price=original_residual_price,
                                buyer_origin=original_bid.buyer_origin,
                                buyer_origin_id=original_bid.buyer_origin_id,
                                buyer_id=original_bid.buyer_id,
                                adapt_price_with_fees=False,
                                add_to_history=True,
                                attributes=original_bid.attributes,
                                requirements=original_bid.requirements,
                                time_slot=original_bid.time_slot)

        log.debug("%s[BID][SPLIT][%s, %s] (%s into %s and %s",
                  self._debug_log_market_type_identifier, self.time_slot_str, self.name,
                  short_offer_bid_log_str(original_bid), short_offer_bid_log_str(accepted_bid),
                  short_offer_bid_log_str(residual_bid))

        self._notify_listeners(MarketEvent.BID_SPLIT,
                               original_bid=original_bid,
                               accepted_bid=accepted_bid,
                               residual_bid=residual_bid)

        return accepted_bid, residual_bid

    def determine_bid_price(self, trade_offer_info, energy):
        _, grid_fee_rate, final_trade_rate = self.fee_class.calculate_trade_price_and_fees(
            trade_offer_info)
        return grid_fee_rate * energy, energy * final_trade_rate

    @lock_market_action
    def accept_bid(self, bid: Bid,
                   energy: Optional[float] = None,
                   seller: Optional[str] = None,
                   buyer: Optional[str] = None,
                   already_tracked: bool = False,
                   trade_rate: Optional[float] = None,
                   trade_offer_info: Optional[TradeBidOfferInfo] = None,
                   seller_origin: Optional[str] = None,
                   seller_origin_id: Optional[str] = None,
                   seller_id: Optional[str] = None) -> Trade:
        market_bid = self.bids.pop(bid.id, None)
        if market_bid is None:
            raise BidNotFoundException("During accept bid: " + str(bid))

        buyer = market_bid.buyer if buyer is None else buyer

        if energy is None or isclose(energy, market_bid.energy, abs_tol=1e-8):
            energy = market_bid.energy

        orig_price = bid.original_price if bid.original_price is not None else bid.price
        residual_bid = None

        if energy <= 0:
            raise InvalidTrade("Energy cannot be negative or zero.")
        if energy > market_bid.energy:
            raise InvalidTrade(f"Traded energy ({energy}) cannot be more than the "
                               f"bid energy ({market_bid.energy}).")
        elif energy < market_bid.energy:
            # partial bid trade
            accepted_bid, residual_bid = self.split_bid(market_bid, energy, orig_price)
            bid = accepted_bid

            # Delete the accepted bid from self.bids:
            try:
                self.bids.pop(accepted_bid.id)
            except KeyError as exception:
                raise BidNotFoundException(
                    f"Bid {accepted_bid.id} not found in self.bids ({self.name}).") from exception
        else:
            # full bid trade, nothing further to do here
            pass

        fee_price, trade_price = self.determine_bid_price(trade_offer_info, energy)
        bid.update_price(trade_price)

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
                      buyer_id=bid.buyer_id, time_slot=bid.time_slot
                      )

        if already_tracked is False:
            self._update_stats_after_trade(trade, bid, already_tracked)
            log.info("%s[TRADE][BID] [%s] [%s] {%s}",
                     self._debug_log_market_type_identifier, self.name, trade.time_slot, trade)

        self._notify_listeners(MarketEvent.BID_TRADED, bid_trade=trade)
        return trade

    def accept_bid_offer_pair(self, bid: Bid, offer: Offer, clearing_rate: float,
                              trade_bid_info: TradeBidOfferInfo,
                              selected_energy: float) -> Tuple[Trade, Trade]:
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
            self, recommendations: List[BidOfferMatch.serializable_dict]) -> bool:
        """Match a list of bid/offer pairs, create trades and residual offers/bids.
        Returns True if trades were actually performed, False otherwise."""
        were_trades_performed = False
        while recommendations:
            recommended_pair = BidOfferMatch.from_dict(recommendations.pop(0))
            market_offer = self.offers.get(recommended_pair.offer["id"])
            market_bid = self.bids.get(recommended_pair.bid["id"])
            try:
                self.validate_bid_offer_match(
                    recommended_pair)
            except InvalidBidOfferPairException as invalid_bop_exception:
                # TODO: Refactor this. The behaviour of the market should not be dependant
                #  on a matching algorithm setting
                if is_external_matching_enabled():
                    # re-raise exception to be handled by the external matcher
                    raise invalid_bop_exception
                continue
            original_bid_rate = market_bid.original_price / market_bid.energy
            trade_bid_info = TradeBidOfferInfo(
                original_bid_rate=original_bid_rate,
                propagated_bid_rate=market_bid.energy_rate,
                original_offer_rate=market_offer.original_price / market_offer.energy,
                propagated_offer_rate=market_offer.energy_rate,
                trade_rate=original_bid_rate)

            bid_trade, offer_trade = self.accept_bid_offer_pair(
                market_bid, market_offer, recommended_pair.trade_rate,
                trade_bid_info, min(recommended_pair.selected_energy,
                                    market_offer.energy, market_bid.energy))
            were_trades_performed = True
            recommendations = (
                self._replace_offers_bids_with_residual_in_recommendations_list(
                    recommendations, offer_trade, bid_trade)
            )
        return were_trades_performed

    @staticmethod
    def _validate_requirements_satisfied(
            recommendation: BidOfferMatch) -> None:
        """Validate if both trade parties satisfy each other's requirements.

        :raises:
            InvalidBidOfferPairException: Bid offer pair failed the validation
        """
        requirements_satisfied = True
        if (recommendation.matching_requirements or {}).get("offer_requirement"):
            offer_requirement = recommendation.matching_requirements["offer_requirement"]
            requirements_satisfied &= RequirementsSatisfiedChecker.is_offer_requirement_satisfied(
                recommendation.offer, recommendation.bid, offer_requirement,
                recommendation.trade_rate, recommendation.selected_energy)
        if (recommendation.matching_requirements or {}).get("bid_requirement"):
            bid_requirement = recommendation.matching_requirements["bid_requirement"]
            requirements_satisfied &= RequirementsSatisfiedChecker.is_bid_requirement_satisfied(
                    recommendation.offer, recommendation.bid, bid_requirement,
                    recommendation.trade_rate, recommendation.selected_energy)
        if not requirements_satisfied:
            # If requirements are not satisfied
            raise InvalidBidOfferPairException(
                "The requirements failed the validation.")

    def validate_bid_offer_match(
            self, recommendation: BidOfferMatch) -> None:
        """Basic validation function for a bid against an offer.

        Raises:
            InvalidBidOfferPairException: Bid offer pair failed the validation
        """
        selected_energy = recommendation.selected_energy
        clearing_rate = recommendation.trade_rate
        market_offer = self.offers.get(recommendation.offer["id"])
        market_bid = self.bids.get(recommendation.bid["id"])

        if not (market_offer and market_bid):
            # If not all offers bids exist in the market, skip the current recommendation
            raise InvalidBidOfferPairException("Not all bids and offers exist in the market.")
        bid_energy = recommendation.bid_energy
        offer_energy = market_offer.energy
        if selected_energy > bid_energy:
            raise InvalidBidOfferPairException(
                f"Energy traded {selected_energy} is higher than bids energy {bid_energy}.")
        if selected_energy > offer_energy:
            raise InvalidBidOfferPairException(
                f"Energy traded {selected_energy} is higher than offers energy {offer_energy}.")
        if recommendation.bid_energy_rate + FLOATING_POINT_TOLERANCE < clearing_rate:
            raise InvalidBidOfferPairException(
                f"Trade rate {clearing_rate} is higher than bid energy rate "
                f"{recommendation.bid_energy_rate}.")
        if market_offer.energy_rate > clearing_rate + FLOATING_POINT_TOLERANCE:
            raise InvalidBidOfferPairException(
                f"Trade rate {clearing_rate} is higher than offer energy rate "
                f"{market_offer.energy_rate}.")

        self._validate_requirements_satisfied(recommendation)

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
            if recommendation["offer"]["id"] == offer_trade.offer_bid.id:
                recommendation["offer"] = offer_trade.residual.serializable_dict()
            if recommendation["bid"]["id"] == bid_trade.offer_bid.id:
                recommendation["bid"] = bid_trade.residual.serializable_dict()
            return recommendation

        if offer_trade.residual or bid_trade.residual:
            recommendations = [replace_recommendations_with_residuals(recommendation)
                               for recommendation in recommendations]
        return recommendations
