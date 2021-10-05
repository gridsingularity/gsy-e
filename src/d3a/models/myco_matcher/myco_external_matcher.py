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

import json
import logging
from enum import Enum
from typing import Dict, List, Optional

from d3a_interface.data_classes import BidOfferMatch

import d3a.constants
from d3a.d3a_core.exceptions import (
    InvalidBidOfferPairException, MycoValidationException)
from d3a.d3a_core.redis_connections.redis_area_market_communicator import ResettableCommunicator
from d3a.models.market.two_sided import TwoSidedMarket
from d3a.models.myco_matcher.myco_matcher_interface import MycoMatcherInterface


class ExternalMatcherEventsEnum(Enum):
    OFFERS_BIDS_RESPONSE = "offers_bids_response"
    MATCH = "match"
    TICK = "tick"
    MARKET = "market_cycle"
    FINISH = "finish"


class MycoExternalMatcher(MycoMatcherInterface):
    """Class responsible for external bids / offers matching."""
    def __init__(self):
        super().__init__()
        self.simulation_id = d3a.constants.CONFIGURATION_ID
        self.myco_ext_conn = None
        self._channel_prefix = f"external-myco/{self.simulation_id}"
        self._events_channel = f"{self._channel_prefix}/events/"
        self._setup_redis_connection()
        self.markets_mapping: Dict[str, TwoSidedMarket] = {}  # Dict[market_id: market] mapping

    def _setup_redis_connection(self):
        self.myco_ext_conn = ResettableCommunicator()
        self.myco_ext_conn.sub_to_multiple_channels(
            {"external-myco/simulation-id/": self.publish_simulation_id,
             f"{self._channel_prefix}/offers-bids/": self.publish_offers_bids,
             f"{self._channel_prefix}/recommendations/": self.match_recommendations})

    def publish_offers_bids(self, message):
        """Publish open offers and bids.

        Published data are of the following format:
            {"bids_offers": {"market_id" : {"bids": [], "offers": [] }, filters: {}}}
        """
        response_data = {"event": ExternalMatcherEventsEnum.OFFERS_BIDS_RESPONSE.value}
        data = json.loads(message.get("data"))
        filters = data.get("filters", {})
        # IDs of markets (Areas) the client is interested in
        filtered_areas_uuids = filters.get("markets")
        market_offers_bids_list_mapping = {}
        for area_uuid, area_data in self.area_uuid_markets_mapping.items():
            if filtered_areas_uuids and area_uuid not in filtered_areas_uuids:
                # Client is uninterested in this Area -> skip
                continue
            for market in area_data["markets"]:
                # Cache the market (needed while matching)
                self.markets_mapping[market.id] = market
                bids_list, offers_list = self._get_bids_offers(market, filters)
                market_offers_bids_list_mapping[market.id] = {
                    "bids": bids_list, "offers": offers_list}
        self.area_uuid_markets_mapping = {}
        response_data.update({
            "bids_offers": market_offers_bids_list_mapping,
        })

        channel = f"{self._channel_prefix}/offers-bids/response/"
        self.myco_ext_conn.publish_json(channel, response_data)

    def match_recommendations(self, message: Optional[dict] = None) -> None:
        """Receive trade recommendations and match them in the relevant market.

        Match in bulk, any pair that fails validation will cancel the operation
        """
        if not message:
            return

        channel = f"{self._channel_prefix}/recommendations/response/"
        response_data = {
            "event": ExternalMatcherEventsEnum.MATCH.value,
            "recommendations": [],
            "status": "success"}
        data = json.loads(message.get("data"))
        recommendations = data.get("recommended_matches", [])
        try:
            self._validate_recommendations(recommendations)
        except MycoValidationException as exception:
            response_data["status"] = "Fail"
            response_data["message"] = f"Validation Error, matching will be skipped: {exception}"
            self.myco_ext_conn.publish_json(channel, response_data)
            return

        for recommendation in recommendations:
            try:
                market = self.markets_mapping.get(recommendation["market_id"])
                market_offers = [
                    market.offers.get(offer["id"]) for offer in recommendation["offers"]]
                market_bids = [market.bids.get(bid["id"]) for bid in recommendation["bids"]]

                if not (all(market_offers) and all(market_bids)):
                    # If not all offers bids exist in the market, skip the current recommendation
                    raise InvalidBidOfferPairException(
                        "Not all bids and offers exist in the market.")

                market.match_recommendations([recommendation])
                response_data["recommendations"].append(
                    {**recommendation, "status": "Success"})
            except InvalidBidOfferPairException as exception:
                response_data["recommendations"].append(
                    {**recommendation, "status": "Fail",
                     "message": str(exception)})
            except Exception:
                response_data["recommendations"].append(
                    {**recommendation, "status": "Fail"})
                logging.exception("Bid offer pair matching failed.")

        self.myco_ext_conn.publish_json(channel, response_data)

    def publish_simulation_id(self, message):
        """Publish the simulation id to the redis myco client.

        At the moment the id of the simulations run by the cli is set as ""
        however, this function guarantees that the myco is aware of the running collaboration id
        regardless of the value set in d3a.
        """

        channel = "external-myco/simulation-id/response/"
        self.myco_ext_conn.publish_json(channel, {"simulation_id": self.simulation_id})

    def event_tick(self, **kwargs):
        """Publish the tick event to the Myco client."""
        is_it_time_for_external_tick = kwargs.pop("is_it_time_for_external_tick", True)
        # If External matching is enabled, limit the number of ticks dispatched.
        if not is_it_time_for_external_tick:
            return
        data = {"event": ExternalMatcherEventsEnum.TICK.value, **kwargs}
        self.myco_ext_conn.publish_json(self._events_channel, data)

    def event_market_cycle(self, **kwargs):
        """Publish the market event to the Myco client and clear finished markets cache.."""

        self.markets_mapping = {}  # clear finished markets
        data = {"event": ExternalMatcherEventsEnum.MARKET.value, **kwargs}
        self.myco_ext_conn.publish_json(self._events_channel, data)

    def event_finish(self, **kwargs):
        """Publish the finish event to the Myco client."""

        data = {"event": ExternalMatcherEventsEnum.FINISH.value}
        self.myco_ext_conn.publish_json(self._events_channel, data)

    @staticmethod
    def _get_bids_offers(market: TwoSidedMarket, filters: Dict):
        """Get bids and offers from market, apply filters and return serializable lists."""

        bids, offers = market.open_bids_and_offers
        bids_list = list(bid.serializable_dict() for bid in bids.values())
        filtered_offers_energy_type = filters.get("energy_type")
        if filtered_offers_energy_type:
            offers_list = list(
                offer.serializable_dict() for offer in offers.values()
                if offer.attributes and
                offer.attributes.get("energy_type") == filtered_offers_energy_type)
        else:
            offers_list = list(
                offer.serializable_dict() for offer in offers.values())
        return bids_list, offers_list

    def _validate_recommendations(
            self, recommendations: List[Dict]) -> None:
        """Validate a list of BidOfferMatch instances.

        Check for conditions that should terminate the matching process.
            - Invalid BidOfferMatch structure
            - Submitting recommendation to an already finished market
        Raises
            MycoValidationException: Condition that is supposed to stop the matching process
        """
        for recommendation in recommendations:
            if not BidOfferMatch.is_valid_dict(recommendation):
                raise MycoValidationException(f"BidOfferMatch is not valid {recommendation}")
            market = self.markets_mapping.get(recommendation.get("market_id"))
            if market is None:
                # The market doesn't exist
                raise MycoValidationException(
                    f"Market with id {recommendation.get('market_id')} doesn't exist."
                    f"{recommendation}")
