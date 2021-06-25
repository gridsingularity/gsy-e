import json
import logging
from typing import Dict

import d3a.constants
from d3a.d3a_core.exceptions import InvalidBidOfferPair
from d3a.d3a_core.redis_connections.redis_area_market_communicator import ResettableCommunicator
from d3a.models.market.market_structures import (
    BidOfferMatch, offer_or_bid_from_json_string)

from d3a.models.myco_matcher.base_matcher import BaseMatcher


class ExternalMatcher(BaseMatcher):
    """Class responsible for external bids / offers matching."""
    def __init__(self):
        super().__init__()
        self.simulation_id = d3a.constants.COLLABORATION_ID
        self.myco_ext_conn = None
        self.channel_prefix = f"external-myco/{self.simulation_id}/"
        self._setup_redis_connection()
        self.area_uuid_markets_mapping = {}
        self.markets_mapping = {}  # Dict[market_id: market] mapping
        self.recommendations = []

    def _setup_redis_connection(self):
        self.myco_ext_conn = ResettableCommunicator()
        self.myco_ext_conn.sub_to_multiple_channels(
            {"external-myco/get-simulation-id": self.publish_simulation_id,
             f"{self.channel_prefix}offers-bids/": self.publish_offers_bids,
             f"{self.channel_prefix}post-recommendations/": self.match_recommendations})

    def publish_offers_bids(self, message):
        """Publish open offers and bids.

        published data are of the following format:
            {"bids_offers": {`market_id` : {"bids": [], "offers": [] }, }}
        """
        response_data = {"event": "offers_bids_response"}
        data = json.loads(message.get("data"))
        filters = data.get("filters", {})
        # IDs of markets the client is interested in
        filtered_market_ids = filters.get("markets", None)
        filtered_offers_energy_type = filters.get("energy_type", None)
        market_offers_bids_list_mapping = {}
        for area_uuid, markets in self.area_uuid_markets_mapping.items():
            if filtered_market_ids and area_uuid not in filtered_market_ids:
                # Client is uninterested in the market -> skip
                continue
            for market in markets:
                # Cache the market (needed while matching)
                self.markets_mapping[market.id] = market
                market_offers_bids_list_mapping[market.id] = {"bids": [], "offers": []}
                bids, offers = market.open_bids_and_offers
                bids_list = list(bid.serializable_dict() for bid in bids.values())

                if filtered_offers_energy_type:
                    offers_list = list(
                        offer.serializable_dict() for offer in offers.values()
                        if offer.attributes and
                        offer.attributes.get("energy_type") == filtered_offers_energy_type)
                else:
                    offers_list = list(
                        offer.serializable_dict() for offer in offers.values())

                market_offers_bids_list_mapping[market.id]["bids"].extend(
                    bids_list)
                market_offers_bids_list_mapping[market.id]["offers"].extend(
                    offers_list)
        response_data.update({
            "bids_offers": market_offers_bids_list_mapping,
        })

        channel = f"{self.channel_prefix}response/offers-bids/"
        self.myco_ext_conn.publish_json(channel, response_data)

    def match_recommendations(self, message):
        """Receive trade recommendations and match them in the relevant market.

        Matching in bulk, any pair that fails validation will cancel the operation
        """
        channel = f"{self.channel_prefix}response/matched-recommendations/"
        response_dict = {"event": "match", "status": "success"}
        data = json.loads(message.get("data"))
        recommendations = data.get("recommended_matches", [])
        validated_records = {}
        for record in recommendations:
            market = self.markets_mapping.get(record.get("market_id"), None)
            if market is None or market.readonly:
                # The market is already finished or doesn't exist
                continue
            bid = offer_or_bid_from_json_string(json.dumps(record.get("bid")))
            offer = offer_or_bid_from_json_string(json.dumps(record.get("offer")),
                                                  record.get("bid").get("time"))

            try:
                if not (offer.id in market.offers and bid.id in market.bids):
                    # Offer or Bid either don't belong to market or were already matched
                    raise InvalidBidOfferPair

                # Get the original bid and offer from the market
                market_bid = market.bids.get(bid.id)
                market_offer = market.offers.get(offer.id)

                market.validate_authentic_bid_offer_pair(
                    market_bid,
                    market_offer,
                    record.get("trade_rate"),
                    record.get("selected_energy")
                    )
                if record.get("market_id") not in validated_records:
                    validated_records[record.get("market_id")] = []

                validated_records[record.get("market_id")].append(BidOfferMatch(
                    market_bid,
                    record.get("selected_energy"),
                    market_offer,
                    record.get("trade_rate")))
            except InvalidBidOfferPair:
                # If validation fails or offer/bid were consumed
                response_dict["status"] = "fail"
                response_dict["message"] = "Validation Error"
                logging.exception("Bid offer pair validation failed.")
                break

        if response_dict["status"] == "success":
            for market_id, records in validated_records.items():
                market = self.markets_mapping.get(market_id)
                if market.readonly:
                    # The market has just finished
                    continue
                market.match_recommendation(records)
        self.myco_ext_conn.publish_json(channel, response_dict)

    def publish_simulation_id(self, message):
        """Publish the simulation id to the redis myco client.

        At the moment the id of the simulations run by the cli is set as ""
        however, this function guarantees that the myco is aware of the running collaboration id
        regardless of the value set in d3a.
        """

        channel = "external-myco/get-simulation-id/response"
        self.myco_ext_conn.publish_json(channel, {"simulation_id": self.simulation_id})

    def publish_event_tick_myco(self):
        """Publish the tick event to the Myco client."""

        channel = f"external-myco/{d3a.constants.COLLABORATION_ID}/response/events/"
        data = {"event": "tick"}
        self.myco_ext_conn.publish_json(channel, data)

    def publish_market_cycle_myco(self):
        """Publish the market event to the Myco client."""

        channel = f"external-myco/{d3a.constants.COLLABORATION_ID}/response/events/"
        data = {"event": "market"}
        self.myco_ext_conn.publish_json(channel, data)

    def publish_event_finish_myco(self):
        """Publish the finish event to the Myco client."""

        channel = f"external-myco/{d3a.constants.COLLABORATION_ID}/response/events/"
        data = {"event": "finish"}
        self.myco_ext_conn.publish_json(channel, data)

    def calculate_match_recommendation(self, bids, offers, current_time=None):
        pass

    def update_area_uuid_markets_mapping(self, area_uuid_markets_mapping: Dict) -> None:
        """Interface for updating the area_uuid_markets_mapping mapping."""
        self.area_uuid_markets_mapping.update(area_uuid_markets_mapping)
