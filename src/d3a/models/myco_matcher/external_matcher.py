import json

import d3a.constants
from d3a.d3a_core.redis_connections.redis_area_market_communicator import ResettableCommunicator
from d3a.models.market import validate_authentic_bid_offer_pair
from d3a.models.market.market_structures import BidOfferMatch
from d3a.models.myco_matcher.base_matcher import BaseMatcher


class ExternalMatcher(BaseMatcher):
    def __init__(self):
        super(ExternalMatcher, self).__init__()
        self.simulation_id = d3a.constants.COLLABORATION_ID
        self.myco_ext_conn = None
        self.channel_prefix = f"external-myco/{self.simulation_id}/"
        self._setup_redis_connection()
        self.area_uuid_markets_mapping = {}
        self.markets_mapping = {}
        self.recommendations = []

    def _setup_redis_connection(self):
        self.myco_ext_conn = ResettableCommunicator()
        self.myco_ext_conn.sub_to_multiple_channels(
            {"external-myco/get_simulation_id": self.get_simulation_id,
             f"{self.channel_prefix}get_offers_bids/": self.publish_offers_bids,
             f"{self.channel_prefix}post_recommendations/": self.match_recommendations})

    def publish_offers_bids(self, message):
        """
        Function that queries publishes open offers and bids
        published data are of the following format
        market_offers_bids_list_mapping = {"market_id" : {"bids": [], "offers": [] }, }
        """
        # TODO: message can contain filters
        data = {"event": "offers_bids_response"}
        market_offers_bids_list_mapping = {}
        for area_uuid, markets in self.area_uuid_markets_mapping.items():
            for market in markets:
                self.markets_mapping[market.id] = market
                market_offers_bids_list_mapping[market.id] = {"bids": [], "offers": []}
                bids, offers = market.open_bids_and_offers
                market_offers_bids_list_mapping[market.id]["bids"].extend(
                    list(bid.serializable_dict() for bid in bids.values()))
                market_offers_bids_list_mapping[market.id]["offers"].extend(
                    list(offer.serializable_dict() for offer in offers.values()))
        data.update({
            "market_offers_bids_list_mapping": market_offers_bids_list_mapping,
        })

        channel = f"{self.channel_prefix}response/get_offers_bids/"
        self.myco_ext_conn.publish_json(channel, data)

    def match_recommendations(self, payload):
        """
        Receive trade recommendations and match them in the relevant market
        """
        data = json.loads(payload.get("data"))
        recommendations = data.get("recommended_matches", [])
        for record in recommendations:
            market = self.markets_mapping.get(record.get("market_id"), None)
            if market is None:
                continue
            validate_authentic_bid_offer_pair(
                record.get("bid"),
                record.get("offer"),
                record.get("trade_rate"),
                record.get("selected_energy")
                )
            market.match_recommendation([BidOfferMatch(
                record.get("bid"),
                record.get("selected_energy"),
                record.get("offer"),
                record.get("trade_rate")), ])
        channel = f"{self.channel_prefix}response/matched_recommendations/"
        data = {"event": "match", "status": "success"}
        self.myco_ext_conn.publish_json(channel, data)

    def calculate_match_recommendation(self, bids, offers, current_time=None):
        pass

    def get_simulation_id(self, message):
        """
        Publish the simulation id to the Myco client
        """
        channel = "external-myco/get_simulation_id/response"
        self.myco_ext_conn.publish_json(channel, {"simulation_id": self.simulation_id})
