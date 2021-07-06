import json
import logging
from typing import Dict, List

from d3a_interface.dataclasses import BidOfferMatch

import d3a.constants
from d3a.d3a_core.exceptions import (
    InvalidBidOfferPairException, OfferNotFoundException,
    BidNotFoundException, MycoValidationException)
from d3a.d3a_core.redis_connections.redis_area_market_communicator import ResettableCommunicator
from d3a.models.market import Market


class ExternalMatcher:
    """Class responsible for external bids / offers matching."""
    def __init__(self):
        super().__init__()
        self.simulation_id = d3a.constants.COLLABORATION_ID
        self.myco_ext_conn = None
        self.channel_prefix = f"external-myco/{self.simulation_id}"
        self.response_channel = f"{self.channel_prefix}/response"
        self.events_channel = f"{self.response_channel}/events/"
        self._setup_redis_connection()
        self.area_uuid_markets_mapping = {}
        self.markets_mapping = {}  # Dict[market_id: market] mapping

    def _setup_redis_connection(self):
        self.myco_ext_conn = ResettableCommunicator()
        self.myco_ext_conn.sub_to_multiple_channels(
            {"external-myco/get-simulation-id": self.publish_simulation_id,
             f"{self.channel_prefix}/offers-bids/": self.publish_offers_bids,
             f"{self.channel_prefix}/post-recommendations/": self.match_recommendations})

    def publish_offers_bids(self, message):
        """Publish open offers and bids.

        published data are of the following format:
            {"bids_offers": {`market_id` : {"bids": [], "offers": [] }, }}
        """
        response_data = {"event": "offers_bids_response"}
        data = json.loads(message.get("data"))
        filters = data.get("filters", {})
        # IDs of markets (Areas) the client is interested in
        filtered_market_ids = filters.get("markets", None)
        market_offers_bids_list_mapping = {}
        for area_id, markets in self.area_uuid_markets_mapping.items():
            if filtered_market_ids and area_id not in filtered_market_ids:
                # Client is uninterested in this Area -> skip
                continue
            for market in markets:
                # Cache the market (needed while matching)
                self.markets_mapping[market.id] = market
                bids_list, offers_list = self._get_bids_offers(market, filters)
                market_offers_bids_list_mapping[market.id] = {
                    "bids": bids_list, "offers": offers_list}
        response_data.update({
            "bids_offers": market_offers_bids_list_mapping,
        })

        channel = f"{self.response_channel}/offers-bids/"
        self.myco_ext_conn.publish_json(channel, response_data)

    def match_recommendations(self, message):
        """Receive trade recommendations and match them in the relevant market.

        Matching in bulk, any pair that fails validation will cancel the operation
        """
        channel = f"{self.response_channel}/matched-recommendations/"
        response_data = {"event": "match", "status": "success"}
        data = json.loads(message.get("data"))
        recommendations = data.get("recommended_matches", [])
        try:
            validated_records = self._get_validated_bid_offer_match_list(recommendations)
            for record in validated_records:
                market = self.markets_mapping.get(record["market_id"])
                try:
                    market.match_recommendations([record])
                except (OfferNotFoundException, BidNotFoundException):
                    # If the offer or bid have just been consumed
                    continue
        except Exception as ex:
            response_data["status"] = "fail"
            response_data["message"] = "Validation Error"
            if not isinstance(ex, MycoValidationException):
                logging.exception("Bid offer pair matching failed.")

        self.myco_ext_conn.publish_json(channel, response_data)

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

        data = {"event": "tick"}
        self.myco_ext_conn.publish_json(self.events_channel, data)

    def publish_event_market_myco(self):
        """Publish the market event to the Myco client."""

        data = {"event": "market"}
        self.myco_ext_conn.publish_json(self.events_channel, data)

    def publish_event_finish_myco(self):
        """Publish the finish event to the Myco client."""

        data = {"event": "finish"}
        self.myco_ext_conn.publish_json(self.events_channel, data)

    def update_area_uuid_markets_mapping(self, area_uuid_markets_mapping: Dict) -> None:
        """Interface for updating the area_uuid_markets_mapping mapping."""
        self.area_uuid_markets_mapping.update(area_uuid_markets_mapping)

    @staticmethod
    def _get_bids_offers(market: Market, filters: Dict):
        """Get bids and offers from market, apply filters and return serializable lists."""

        bids, offers = market.open_bids_and_offers
        bids_list = list(bid.serializable_dict() for bid in bids.values())
        filtered_offers_energy_type = filters.get("energy_type", None)
        if filtered_offers_energy_type:
            offers_list = list(
                offer.serializable_dict() for offer in offers.values()
                if offer.attributes and
                offer.attributes.get("energy_type") == filtered_offers_energy_type)
        else:
            offers_list = list(
                offer.serializable_dict() for offer in offers.values())
        return bids_list, offers_list

    def _get_validated_bid_offer_match_list(
            self, recommendations: List[Dict]) -> List[BidOfferMatch.serializable_dict]:
        """Return a validated list of BidOfferMatch instances."""
        validated_records = []
        for record in recommendations:
            market = self.markets_mapping.get(record.get("market_id"), None)
            if market is None or market.readonly:
                # The market is already finished or doesn't exist
                raise MycoValidationException

            # Get the original bid and offer from the market
            market_bid = market.bids.get(record.get("bid").get("id"), None)
            market_offer = market.offers.get(record.get("offer").get("id"), None)

            if not (market_bid and market_offer):
                # Offer or Bid either don't belong to market or were already matched
                continue
            try:
                market.validate_authentic_bid_offer_pair(
                    market_bid,
                    market_offer,
                    record.get("trade_rate"),
                    record.get("selected_energy")
                )
            except InvalidBidOfferPairException:
                continue

            validated_records.append(BidOfferMatch(
                market_id=record.get("market_id"),
                bid=market_bid.serializable_dict(),
                selected_energy=record.get("selected_energy"),
                offer=market_offer.serializable_dict(),
                trade_rate=record.get("trade_rate"),
                ).serializable_dict())
        return validated_records
