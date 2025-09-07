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
from decimal import Decimal
from logging import getLogger
from math import isclose
from typing import Dict, List, Union, Tuple, Optional

from gsy_framework.constants_limits import ConstSettings, FLOATING_POINT_TOLERANCE
from gsy_framework.data_classes import (
    Bid,
    Offer,
    Trade,
    TradeBidOfferInfo,
    BidOfferMatch,
    TraderDetails,
)
from gsy_framework.enums import BidOfferMatchAlgoEnum
from gsy_framework.matching_algorithms.requirements_validators import RequirementsSatisfiedChecker
from pendulum import DateTime

from gsy_e.events.event_structures import MarketEvent
from gsy_e.gsy_e_core.exceptions import (
    BidNotFoundException,
    InvalidBidOfferPairException,
    InvalidTrade,
    NegativePriceOrdersException,
    NegativeEnergyOrderException,
    NegativeEnergyTradeException,
)
from gsy_e.gsy_e_core.util import short_offer_bid_log_str, is_external_matching_enabled
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

    # pylint: disable=too-many-positional-arguments

    def __init__(
        self,
        time_slot=None,
        bc=None,
        notification_listener=None,
        readonly=False,
        grid_fee_type=ConstSettings.MASettings.GRID_FEE_TYPE,
        grid_fees=None,
        name=None,
        in_sim_duration=True,
    ):
        # pylint: disable=too-many-arguments
        super().__init__(
            time_slot,
            bc,
            notification_listener,
            readonly,
            grid_fee_type,
            grid_fees,
            name,
            in_sim_duration=in_sim_duration,
        )

    @property
    def _debug_log_market_type_identifier(self):
        return "[TWO_SIDED]"

    def __repr__(self):
        return (
            f"<{self._class_name} {self.time_slot_str} bids: {len(self.bids)}"
            f" (E: {sum(b.energy for b in self.bids.values())} kWh"
            f" V:{sum(b.price for b in self.bids.values())}) "
            f"offers: {len(self.offers)} (E: {sum(o.energy for o in self.offers.values())} kWh"
            f" V: {sum(o.price for o in self.offers.values())}) "
            f"trades: {len(self.trades)} (E: {self.accumulated_trade_energy} kWh"
            f", V: {self.accumulated_trade_price})>"
        )

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

    def _update_requirements_prices(self, bid):
        requirements = []
        for requirement in bid.requirements or []:
            updated_requirement = {**requirement}
            if "price" in updated_requirement:
                energy = updated_requirement.get("energy") or bid.energy
                original_bid_price = updated_requirement["price"] + bid.accumulated_grid_fees
                updated_price = (
                    self.fee_class.update_incoming_bid_with_fee(
                        updated_requirement["price"] / energy, original_bid_price / energy
                    )
                ) * energy
                updated_requirement["price"] = updated_price
            requirements.append(updated_requirement)
        return requirements

    @lock_market_action
    def bid(
        self,
        price: float,
        energy: float,
        buyer: TraderDetails,
        bid_id: Optional[str] = None,
        original_price: Optional[float] = None,
        adapt_price_with_fees: bool = True,
        add_to_history: bool = True,
        dispatch_event: bool = True,
        time_slot: Optional[DateTime] = None,
    ) -> Bid:
        """Create bid object."""
        # pylint: disable=too-many-arguments
        if energy <= FLOATING_POINT_TOLERANCE:
            raise NegativeEnergyOrderException("Energy value for bid can not be negative.")

        if not time_slot:
            time_slot = self.time_slot

        if original_price is None:
            original_price = price

        if adapt_price_with_fees:
            price = (
                self.fee_class.update_incoming_bid_with_fee(
                    price / energy, original_price / energy
                )
                * energy
            )

        if price < 0.0:
            raise NegativePriceOrdersException("Negative price after taxes, bid cannot be posted.")

        bid = Bid(
            str(uuid.uuid4()) if bid_id is None else bid_id,
            self.now,
            price,
            energy,
            buyer,
            original_price,
            time_slot=time_slot,
        )

        self.bids[bid.id] = bid
        if add_to_history is True:
            self.bid_history.append(bid)
        if dispatch_event is True:
            self.dispatch_market_bid_event(bid)
        log.debug(
            "%s[BID][NEW][%s][%s] %s",
            self._debug_log_market_type_identifier,
            self.name,
            self.time_slot_str or bid.time_slot,
            bid,
        )
        self.no_new_order = False
        return bid

    def dispatch_market_bid_event(self, bid: Bid) -> None:
        """Dispatch the BID event to the listeners."""
        self._notify_listeners(MarketEvent.BID, bid=bid)

    @lock_market_action
    def delete_bid(self, bid_or_id: Union[str, Bid]):
        """Delete bid object."""
        if isinstance(bid_or_id, Bid):
            bid_or_id = bid_or_id.id
        bid = self.bids.pop(bid_or_id, None)
        if not bid:
            raise BidNotFoundException(bid_or_id)
        log.debug(
            "%s[BID][DEL][%s][%s] %s",
            self._debug_log_market_type_identifier,
            self.name,
            self.time_slot_str or bid.time_slot,
            bid,
        )
        self._notify_listeners(MarketEvent.BID_DELETED, bid=bid)

    def split_bid(self, original_bid: Bid, energy: Decimal, orig_bid_price: Decimal):
        """Split bid into two, one with provided energy, the other with the residual."""

        self.bids.pop(original_bid.id, None)

        # same bid id is used for the new accepted_bid
        original_energy_dec = Decimal(original_bid.energy)
        original_accepted_price = energy / original_energy_dec * orig_bid_price

        accepted_bid = self.bid(
            bid_id=original_bid.id,
            price=float(orig_bid_price * (energy / original_energy_dec)),
            energy=float(energy),
            buyer=original_bid.buyer,
            original_price=float(original_accepted_price),
            adapt_price_with_fees=False,
            add_to_history=False,
            dispatch_event=False,
            time_slot=original_bid.time_slot,
        )

        residual_price = (Decimal(1) - energy / original_energy_dec) * orig_bid_price
        residual_energy = original_energy_dec - energy

        original_residual_price = (
            (original_energy_dec - energy) / original_energy_dec
        ) * orig_bid_price

        residual_bid = self.bid(
            price=float(residual_price),
            energy=float(residual_energy),
            buyer=original_bid.buyer,
            original_price=float(original_residual_price),
            adapt_price_with_fees=False,
            add_to_history=True,
            dispatch_event=False,
            time_slot=original_bid.time_slot,
        )

        log.debug(
            "%s[BID][SPLIT][%s, %s] (%s into %s and %s",
            self._debug_log_market_type_identifier,
            self.time_slot_str or residual_bid.time_slot,
            self.name,
            short_offer_bid_log_str(original_bid),
            short_offer_bid_log_str(accepted_bid),
            short_offer_bid_log_str(residual_bid),
        )

        self._notify_listeners(
            MarketEvent.BID_SPLIT,
            original_bid=original_bid,
            accepted_bid=accepted_bid,
            residual_bid=residual_bid,
        )

        return accepted_bid, residual_bid

    def _determine_bid_price(self, trade_offer_info, energy: Decimal) -> Tuple[Decimal, Decimal]:
        _, grid_fee_rate, final_trade_rate = self.fee_class.calculate_trade_price_and_fees(
            trade_offer_info
        )

        return grid_fee_rate * energy, energy * final_trade_rate

    @lock_market_action
    def accept_bid(
        self,
        bid: Bid,
        energy: Optional[float] = None,
        seller: Optional[TraderDetails] = None,
        buyer: Optional[TraderDetails] = None,
        trade_offer_info: Optional[TradeBidOfferInfo] = None,
        offer: Offer = None,
    ) -> Trade:
        """Accept bid and create Trade object."""
        # pylint: disable=too-many-arguments, too-many-locals
        market_bid = self.bids.pop(bid.id, None)
        if market_bid is None:
            raise BidNotFoundException("During accept bid: " + str(bid))

        buyer = market_bid.buyer if buyer is None else buyer

        if energy is None or isclose(energy, market_bid.energy, abs_tol=1e-8):
            energy = market_bid.energy

        orig_price = bid.original_price if bid.original_price is not None else bid.price
        residual_bid = None

        energy_dec = Decimal(energy)
        market_bid_energy_dec = Decimal(market_bid.energy)
        orig_price_dec = Decimal(orig_price)

        if energy <= 0:
            raise NegativeEnergyTradeException("Energy cannot be negative or zero.")
        if market_bid_energy_dec - energy_dec < -FLOATING_POINT_TOLERANCE:
            raise InvalidTrade(
                f"Traded energy ({energy_dec}) cannot be more than the "
                f"bid energy ({market_bid_energy_dec})."
            )
        if market_bid_energy_dec - energy_dec > FLOATING_POINT_TOLERANCE:
            # partial bid trade
            accepted_bid, residual_bid = self.split_bid(market_bid, energy_dec, orig_price_dec)
            bid = accepted_bid

            # Delete the accepted bid from self.bids:
            try:
                self.bids.pop(accepted_bid.id)
            except KeyError as exception:
                raise BidNotFoundException(
                    f"Bid {accepted_bid.id} not found in self.bids ({self.name})."
                ) from exception
        else:
            # full bid trade, nothing further to do here
            pass

        fee_price, trade_price = self._determine_bid_price(trade_offer_info, energy_dec)
        bid.update_price(float(trade_price))

        # Do not adapt grid fees when creating the bid_trade_info structure, to mimic
        # the behavior of the forwarded bids which use the source market fee.
        updated_bid_trade_info = self.fee_class.propagate_original_offer_info_on_bid_trade(
            trade_offer_info, ignore_fees=True
        )

        trade = Trade(
            str(uuid.uuid4()),
            self.now,
            seller,
            bid.buyer,
            bid=bid,
            offer=offer,
            traded_energy=energy,
            trade_price=float(trade_price),
            residual=residual_bid,
            offer_bid_trade_info=updated_bid_trade_info,
            fee_price=float(fee_price),
            time_slot=bid.time_slot,
        )

        if not offer:
            # This is a chain trade, therefore needs to be tracked. For the trade on the market
            # that the match is performed, the tracking should have already been done by the offer
            # trade.
            self._update_stats_after_trade(trade, bid)
            log.info(
                "%s[TRADE][BID] [%s] [%s] {%s}",
                self._debug_log_market_type_identifier,
                self.name,
                trade.time_slot,
                trade,
            )

        self._notify_listeners(MarketEvent.BID_TRADED, bid_trade=trade)
        if residual_bid:
            self.dispatch_market_bid_event(residual_bid)
        return trade

    def accept_bid_offer_pair(
        self,
        bid: Bid,
        offer: Offer,
        clearing_rate: float,
        trade_bid_info: TradeBidOfferInfo,
        selected_energy: float,
    ) -> Tuple[Trade, Trade]:
        """Accept bid and offers in pair when a trade is happening."""
        # pylint: disable=too-many-arguments
        assert isclose(clearing_rate, trade_bid_info.trade_rate)
        assert bid.buyer.uuid != offer.seller.uuid
        trade = self.accept_offer(
            offer_or_id=offer,
            buyer=bid.buyer,
            energy=selected_energy,
            trade_bid_info=trade_bid_info,
            bid=bid,
        )

        bid_trade = self.accept_bid(
            bid=bid,
            energy=selected_energy,
            seller=offer.seller,
            buyer=bid.buyer,
            trade_offer_info=trade_bid_info,
            offer=offer,
        )
        return bid_trade, trade

    def _get_offer_from_seller_origin_id(self, seller_origin_id):
        """Get the first offer that has the same seller_origin_id."""
        if seller_origin_id is None:
            # Many offers may have seller_origin_id=None; Avoid looking for them as it is
            # inaccurate.
            return None

        return next(
            iter(
                [
                    offer
                    for offer in self.offers.values()
                    if offer.seller.origin_uuid == seller_origin_id
                ]
            ),
            None,
        )

    def _get_bid_from_buyer_origin_id(self, buyer_origin_id):
        if buyer_origin_id is None:
            # Many bids may have buyer_origin_id=None; Avoid looking for them as it is inaccurate.
            return None

        return next(
            iter([bid for bid in self.bids.values() if bid.buyer.origin_uuid == buyer_origin_id]),
            None,
        )

    def match_recommendations(
        self, recommendations: List[BidOfferMatch.serializable_dict]
    ) -> bool:
        """
        Match a list of bid/offer pairs, create trades and residual offers/bids.
        Returns True if trades were actually performed, False otherwise.
        """
        # pylint: disable=fixme
        were_trades_performed = False
        while recommendations:
            recommended_pair = BidOfferMatch.from_dict(recommendations.pop(0))

            market_offer = self.offers.get(recommended_pair.offer["id"])
            # TODO: This is a temporary solution based on the fact that trading strategies do not
            # post multiple bids or offers on the same market at the moment. Will be shortly
            # replaced by a global offer / bid identifier instead of tracking the original order
            # by seller / buyer.
            if not market_offer:
                market_offer = self._get_offer_from_seller_origin_id(
                    recommended_pair.offer["seller"]["origin_uuid"]
                )
                if market_offer is None:
                    raise InvalidBidOfferPairException("Offer does not exist in the market")
            recommended_pair.offer = market_offer.serializable_dict()

            market_bid = self.bids.get(recommended_pair.bid["id"])
            if not market_bid:
                market_bid = self._get_bid_from_buyer_origin_id(
                    recommended_pair.bid["buyer"]["origin_uuid"]
                )
                if market_bid is None:
                    raise InvalidBidOfferPairException("Bid does not exist in the market")
            recommended_pair.bid = market_bid.serializable_dict()

            if market_offer.seller.uuid == market_bid.buyer.uuid:
                # Cannot clear a bid with an offer from the same direct origin.
                continue

            try:
                self.validate_bid_offer_match(recommended_pair)
            except InvalidBidOfferPairException as invalid_bop_exception:
                # TODO: Refactor this. The behaviour of the market should not be dependant
                #  on a matching algorithm setting
                if is_external_matching_enabled():
                    # re-raise exception to be handled by the external matcher
                    raise invalid_bop_exception
                continue
            original_bid_rate = recommended_pair.bid_energy_rate + (
                market_bid.accumulated_grid_fees / recommended_pair.bid_energy
            )
            if (
                ConstSettings.MASettings.BID_OFFER_MATCH_TYPE
                == BidOfferMatchAlgoEnum.PAY_AS_BID.value
            ):
                trade_rate = original_bid_rate
            else:
                trade_rate = self.fee_class.calculate_original_trade_rate_from_clearing_rate(
                    original_bid_rate, market_bid.energy_rate, recommended_pair.trade_rate
                )
            trade_bid_info = TradeBidOfferInfo(
                original_bid_rate=original_bid_rate,
                propagated_bid_rate=recommended_pair.bid_energy_rate,
                original_offer_rate=market_offer.original_energy_rate,
                propagated_offer_rate=market_offer.energy_rate,
                trade_rate=trade_rate,
            )

            bid_trade, offer_trade = self.accept_bid_offer_pair(
                market_bid,
                market_offer,
                trade_rate,
                trade_bid_info,
                min(recommended_pair.selected_energy, market_offer.energy, market_bid.energy),
            )
            were_trades_performed = True
            recommendations = self._replace_offers_bids_with_residual_in_recommendations_list(
                recommendations, offer_trade, bid_trade
            )
        return were_trades_performed

    @staticmethod
    def _validate_requirements_satisfied(recommendation: BidOfferMatch) -> None:
        """Validate if both trade parties satisfy each other's requirements.

        :raises:
            InvalidBidOfferPairException: Bid offer pair failed the validation
        """
        requirements_satisfied = True
        if (recommendation.matching_requirements or {}).get("offer_requirement"):
            offer_requirement = recommendation.matching_requirements["offer_requirement"]
            requirements_satisfied &= RequirementsSatisfiedChecker.is_offer_requirement_satisfied(
                recommendation.offer,
                recommendation.bid,
                offer_requirement,
                recommendation.trade_rate,
                recommendation.selected_energy,
            )
        if (recommendation.matching_requirements or {}).get("bid_requirement"):
            bid_requirement = recommendation.matching_requirements["bid_requirement"]
            requirements_satisfied &= RequirementsSatisfiedChecker.is_bid_requirement_satisfied(
                recommendation.offer,
                recommendation.bid,
                bid_requirement,
                recommendation.trade_rate,
                recommendation.selected_energy,
            )
        if not requirements_satisfied:
            # If requirements are not satisfied
            raise InvalidBidOfferPairException("The requirements failed the validation.")

    def validate_bid_offer_match(self, recommendation: BidOfferMatch) -> None:
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
        if selected_energy <= 0:
            raise InvalidBidOfferPairException(
                f"Energy traded {selected_energy} should be more than 0."
            )
        if selected_energy > bid_energy:
            raise InvalidBidOfferPairException(
                f"Energy traded {selected_energy} is higher than bids energy {bid_energy}."
            )
        if selected_energy > offer_energy:
            raise InvalidBidOfferPairException(
                f"Energy traded {selected_energy} is higher than offers energy {offer_energy}."
            )
        if recommendation.bid_energy_rate + FLOATING_POINT_TOLERANCE < clearing_rate:
            raise InvalidBidOfferPairException(
                f"Trade rate {clearing_rate} is higher than bid energy rate "
                f"{recommendation.bid_energy_rate}."
            )
        if market_offer.energy_rate > clearing_rate + FLOATING_POINT_TOLERANCE:
            raise InvalidBidOfferPairException(
                f"Trade rate {clearing_rate} is lower than offer energy rate "
                f"{market_offer.energy_rate}."
            )

        self._validate_matching_requirements(recommendation)
        self._validate_requirements_satisfied(recommendation)

    @staticmethod
    def _validate_matching_requirements(recommendation: BidOfferMatch) -> None:
        """Validate a matching_requirement actually exists in the Bid/Offer object.

        Raises:
            InvalidBidOfferPairException: matching_requirement doesn't exist in the Bid/Offer
            object.
        """
        if not recommendation.matching_requirements:
            return

        bid_matching_requirement = recommendation.matching_requirements.get("bid_requirement")
        if bid_matching_requirement:
            bid_requirements = recommendation.bid.get("requirements") or []
            if bid_matching_requirement not in bid_requirements:
                raise InvalidBidOfferPairException(
                    f"Matching requirement {bid_matching_requirement} doesn't exist in the Bid"
                    " object."
                )

        offer_matching_requirement = recommendation.matching_requirements.get("offer_requirement")
        if offer_matching_requirement:
            offer_requirements = recommendation.offer.get("requirements") or []
            if offer_matching_requirement not in offer_requirements:
                raise InvalidBidOfferPairException(
                    f"Matching requirement {offer_matching_requirement} doesn't exist in the Offer"
                    f" object."
                )

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

        def _adapt_matching_requirements_in_residuals(recommendation):
            if "energy" in (recommendation.get("matching_requirements") or {}).get(
                "bid_requirement", {}
            ):
                for index, requirement in enumerate(recommendation["bid"]["requirements"]):
                    if requirement == recommendation["matching_requirements"]["bid_requirement"]:
                        bid_requirement = deepcopy(requirement)
                        bid_requirement["energy"] -= bid_trade.traded_energy
                        recommendation["bid"]["requirements"][index] = bid_requirement
                        recommendation["matching_requirements"][
                            "bid_requirement"
                        ] = bid_requirement
                        return recommendation
            return recommendation

        def replace_recommendations_with_residuals(recommendation: Dict):
            if (
                recommendation["offer"]["id"] == offer_trade.match_details["offer"].id
                and offer_trade.residual is not None
            ):
                recommendation["offer"] = offer_trade.residual.serializable_dict()
            if (
                recommendation["bid"]["id"] == bid_trade.match_details["bid"].id
                and bid_trade.residual is not None
            ):
                recommendation["bid"] = bid_trade.residual.serializable_dict()
                recommendation = _adapt_matching_requirements_in_residuals(recommendation)

            return recommendation

        if offer_trade.residual or bid_trade.residual:
            recommendations = [
                replace_recommendations_with_residuals(recommendation)
                for recommendation in recommendations
            ]
        return recommendations
