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
import json
import logging
from copy import copy
from enum import Enum
from typing import Dict, List

from gsy_framework.constants_limits import GlobalConfig
from gsy_framework.data_classes import BidOfferMatch

import gsy_e.constants
from gsy_e.gsy_e_core.exceptions import (
    InvalidBidOfferPairException, MycoValidationException)
from gsy_e.gsy_e_core.redis_connections.redis_area_market_communicator import (
    myco_redis_communicator_factory)
from gsy_e.gsy_e_core.util import ExternalTickCounter
from gsy_e.models.market.two_sided import TwoSidedMarket
from gsy_e.models.myco_matcher.myco_matcher_interface import MycoMatcherInterface


# pylint: disable=fixme


class ExternalMatcherEventsEnum(Enum):
    """Enum for all events of the external matcher."""
    OFFERS_BIDS_RESPONSE = "offers_bids_response"
    MATCH = "match"
    TICK = "tick"
    MARKET = "market_cycle"
    FINISH = "finish"


# pylint: disable=too-many-instance-attributes
class MycoExternalMatcher(MycoMatcherInterface):
    """Class responsible for external bids / offers matching."""
    def __init__(self):
        super().__init__()
        self.simulation_id = gsy_e.constants.CONFIGURATION_ID

        # Dict[area_id-time_slot_str: market] mapping
        self.area_markets_mapping: Dict[str, TwoSidedMarket] = {}
        self._recommendations = []
        self._publish_orders_message_buffer = []

        self._tick_counter = ExternalTickCounter(
            GlobalConfig.ticks_per_slot,
            gsy_e.constants.DISPATCH_MYCO_EVENT_TICK_FREQUENCY_PERCENT
        )

        self.myco_ext_conn = None
        self._channel_prefix = f"external-myco/{self.simulation_id}"
        self._events_channel = f"{self._channel_prefix}/events/"
        self._setup_redis_connection()

    def _setup_redis_connection(self):
        self.myco_ext_conn = myco_redis_communicator_factory()
        self.myco_ext_conn.sub_to_multiple_channels(
            {"external-myco/simulation-id/": self.publish_simulation_id,
             f"{self._channel_prefix}/offers-bids/": self._publish_orders_message_buffer.append,
             f"{self._channel_prefix}/recommendations/": self._populate_recommendations})

    def _publish_orders(self):
        """Publish open offers and bids.

        Published data are of the following format:
        {"bids_offers": {'area_uuid' : {'time_slot': {"bids": [], "offers": []}}}}

        """
        # Copy the original buffer in order to avoid concurrent access from the Redis thread
        publish_orders = copy(self._publish_orders_message_buffer)
        self._publish_orders_message_buffer.clear()

        for message in publish_orders:
            data = json.loads(message.get("data"))
            response_data = {"event": ExternalMatcherEventsEnum.OFFERS_BIDS_RESPONSE.value}
            filters = data.get("filters", {})
            # IDs of markets (Areas) the client is interested in
            filtered_areas_uuids = filters.get("markets")
            market_orders_list_mapping = {}
            for area_uuid, area_data in self.area_uuid_markets_mapping.items():
                if filtered_areas_uuids and area_uuid not in filtered_areas_uuids:
                    # Client is uninterested in this Area -> skip
                    continue

                # Cache the market (needed while matching)
                for market in area_data["markets"] + area_data.get("settlement_markets", []):
                    self.area_markets_mapping.update(
                        {f"{area_uuid}-{market.time_slot_str}": market})
                    if area_uuid not in market_orders_list_mapping:
                        market_orders_list_mapping[area_uuid] = {}
                    market_orders_list_mapping[area_uuid].update(
                        self._get_orders(market, filters))

                if area_data.get("future_markets"):
                    # Future markets
                    market = area_data["future_markets"]
                    self.area_markets_mapping.update(
                        {f"{area_uuid}-{time_slot_str}": market
                         for time_slot_str in market.orders_per_slot().keys()})
                    if area_uuid not in market_orders_list_mapping:
                        market_orders_list_mapping[area_uuid] = {}
                    market_orders_list_mapping[area_uuid].update(
                        self._get_orders(market, filters))

            self.area_uuid_markets_mapping = {}
            # TODO: change the `bids_offers` key and the channel to `orders`
            response_data.update({
                "bids_offers": market_orders_list_mapping,
            })

            channel = f"{self._channel_prefix}/offers-bids/response/"
            self.myco_ext_conn.publish_json(channel, response_data)

    def _populate_recommendations(self, message):
        """Receive trade recommendations and store them to be consumed in a later stage."""
        data = json.loads(message.get("data"))
        recommendations = data.get("recommended_matches", [])
        self._recommendations.extend(recommendations)

    def match_recommendations(self, **kwargs) -> None:
        """Consume trade recommendations and match them in the relevant market.

        Validate recommendations and if any pair raised a blocking exception
         ie. InvalidBidOfferPairException the matching will be cancelled.
        """
        channel = f"{self._channel_prefix}/recommendations/response/"
        response_data = {
            "event": ExternalMatcherEventsEnum.MATCH.value,
            "status": "success"}

        recommendations = self._recommendations
        if len(recommendations) == 0:
            return
        response_data.update(
            MycoExternalMatcherValidator.validate_and_report(self, recommendations))
        if response_data["status"] != "success":
            logging.debug("All recommendations failed: %s", response_data)
            self.myco_ext_conn.publish_json(channel, response_data)
            self._recommendations = []
            return

        for recommendation in response_data["recommendations"]:
            try:
                if recommendation["status"] != "success":
                    logging.debug("Ignoring recommendation: %s", recommendation)
                    continue
                recommendation.pop("status")
                # market_id refers to the area_id (Area that has no strategy)
                # TODO: rename market_id to area_id in the BidOfferMatch dataclass
                market = self.area_markets_mapping.get(
                    f"{recommendation['market_id']}-{recommendation['time_slot']}")
                were_trades_performed = market.match_recommendations([recommendation])
                if were_trades_performed:
                    recommendation["status"] = "success"
                else:
                    recommendation["status"] = "fail"
            except InvalidBidOfferPairException as exception:
                recommendation["status"] = "fail"
                recommendation["message"] = str(exception)
                continue
        self._recommendations = []
        self.myco_ext_conn.publish_json(channel, response_data)

    def publish_simulation_id(self, _):
        """Publish the simulation id to the redis myco client.

        At the moment the id of the simulations run by the cli is set as ""
        however, this function guarantees that the myco is aware of the running collaboration id
        regardless of the value set in gsy_e.
        """

        channel = "external-myco/simulation-id/response/"
        self.myco_ext_conn.publish_json(channel, {"simulation_id": self.simulation_id})

    def event_tick(self, **kwargs):
        """
        Publish the tick event to the Myco client. Should be performed after the tick event from
        all areas has been completed.
        """
        current_tick_in_slot = kwargs.pop("current_tick_in_slot", 0)
        # If External matching is enabled, limit the number of ticks dispatched.
        if not self._tick_counter.is_it_time_for_external_tick(current_tick_in_slot):
            return
        data = {"event": ExternalMatcherEventsEnum.TICK.value, **kwargs}
        self.myco_ext_conn.publish_json(self._events_channel, data)
        # Publish the orders of the market at the end of the tick, in order for the external
        # commands and aggregator commands to have already been processed
        self._publish_orders()

    def event_market_cycle(self, **kwargs):
        """Publish the market event to the Myco client and clear finished markets cache."""

        self.area_markets_mapping = {}  # clear finished markets
        data = {"event": ExternalMatcherEventsEnum.MARKET.value, **kwargs}
        self.myco_ext_conn.publish_json(self._events_channel, data)

    def event_finish(self, **kwargs):
        """Publish the finish event to the Myco client."""

        data = {"event": ExternalMatcherEventsEnum.FINISH.value}
        self.myco_ext_conn.publish_json(self._events_channel, data)

    @staticmethod
    def _get_orders(market: TwoSidedMarket, filters: Dict) -> Dict:
        """Get bids and offers from market, apply filters and return serializable lists."""

        orders = market.orders_per_slot()
        filtered_energy_type = filters.get("energy_type")
        if filtered_energy_type:
            for orders_values in orders.values():
                offers_list = []
                for offer in orders_values["offers"]:
                    if offer.get("attributes") and offer["attributes"].get(
                            "energy_type") == filtered_energy_type:
                        offers_list.append(offer)
                orders_values["offers"] = offers_list
        return orders


class MycoExternalMatcherValidator:
    """Class responsible for the validation of external recommendations."""

    # Blocking exceptions are ones that should block the matching process
    BLOCKING_EXCEPTIONS = (MycoValidationException, )

    @staticmethod
    def _validate_valid_dict(_: MycoExternalMatcher, recommendation: Dict):
        """Check whether the recommendation dict is valid."""
        if not BidOfferMatch.is_valid_dict(recommendation):
            raise MycoValidationException(f"BidOfferMatch is not valid {recommendation}")

    @staticmethod
    def _validate_market_exists(matcher: MycoExternalMatcher, recommendation: Dict):
        """Check whether myco matcher is keeping track of the received market id"""
        market = matcher.area_markets_mapping.get(
            f"{recommendation.get('market_id')}-{recommendation.get('time_slot')}")
        if market is None:
            # The market doesn't exist
            raise MycoValidationException(
                f"Market with id {recommendation.get('market_id')} "
                f"and time slot {recommendation.get('time_slot')} doesn't exist."
                f"{recommendation}")

    @staticmethod
    def _validate_orders_exist_in_market(matcher: MycoExternalMatcher, recommendation: Dict):
        """Check whether all bids/offers exist in the market."""

        market = matcher.area_markets_mapping.get(
            f"{recommendation.get('market_id')}-{recommendation.get('time_slot')}")
        market_offer = market.offers.get(recommendation["offer"]["id"])
        market_bid = market.bids.get(recommendation["bid"]["id"])

        if not (market_offer and market_bid):
            # If not all offers bids exist in the market, skip the current recommendation
            raise InvalidBidOfferPairException(
                "Not all bids and offers exist in the market.")

    @classmethod
    def _validate(cls, matcher: MycoExternalMatcher, recommendation: Dict):
        """Call corresponding validation methods."""
        cls._validate_valid_dict(matcher, recommendation)
        cls._validate_market_exists(matcher, recommendation)
        cls._validate_orders_exist_in_market(matcher, recommendation)

    @classmethod
    def validate_and_report(cls, matcher: MycoExternalMatcher, recommendations: List) -> Dict:
        """Validate recommendations and return a detailed report."""

        response = {"status": "success", "recommendations": []}
        for recommendation in recommendations:
            try:
                cls._validate(matcher, recommendation)
                response["recommendations"].append(
                    {**recommendation, "status": "success"}
                )
            except (MycoValidationException, InvalidBidOfferPairException) as exception:
                if isinstance(exception, cls.BLOCKING_EXCEPTIONS):
                    response["status"] = "fail"
                    response[
                        "message"] = f"Validation Error, matching will be skipped: {exception}"
                    break
                response["recommendations"].append(
                    {**recommendation, "status": "fail", "message": str(exception)})
                continue
        return response
