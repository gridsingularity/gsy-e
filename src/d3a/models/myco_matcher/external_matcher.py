import json

import d3a.constants
from d3a.d3a_core.redis_connections.redis_area_market_communicator import RedisCommunicator
from d3a.models.market import validate_authentic_bid_offer_pair
from d3a.models.market.market_structures import BidOfferMatch
from d3a.models.myco_matcher.base_matcher import BaseMatcher


class ExternalMatcher(BaseMatcher):
    def __init__(self):
        super(ExternalMatcher, self).__init__()
        self.job_uuid = d3a.constants.COLLABORATION_ID
        self.myco_ext_conn = None
        self.channel_prefix = f"external-myco/{self.job_uuid}/"
        self._setup_redis_connection()
        self.area_uuid_markets_mapping = {}
        self.markets_mapping = {}
        self.recommendations = []

    def _setup_redis_connection(self):
        self.myco_ext_conn = RedisCommunicator()
        self.myco_ext_conn.sub_to_channel("external-myco/get_job_uuid",
                                          self.get_job_uuid)
        self.myco_ext_conn.sub_to_channel(f"{self.channel_prefix}get_offers_bids/",
                                          self.publish_offers_bids)
        self.myco_ext_conn.sub_to_channel(f"{self.channel_prefix}post_recommendations/",
                                          self.match_recommendations)

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
        self.myco_ext_conn.publish(channel, json.dumps(data))

    def match_recommendations(self, message):
        for record in message["data"]:
            market = self.markets_mapping[record["market_id"]]
            validate_authentic_bid_offer_pair(
                record.get("bid"),
                record.get("offer"),
                record.get("trade_rate"),
                record.get("selected_energy")
                )
            market.match_recommendations([BidOfferMatch(record.get("bid"),
                                                        record.get("selected_energy"),
                                                        record.get("offer"),
                                                        record.get("trade_rate")), ])
        channel = f"{self.channel_prefix}response/matched_recommendations/"
        self.myco_ext_conn.publish(channel, json.dumps({"event": "match", "status": "success"}))

    def calculate_match_recommendation(self, bids, offers, current_time=None):
        pass

    def get_job_uuid(self, message):
        channel = "external-myco/get_job_uuid/response"
        self.myco_ext_conn.publish(channel, json.dumps({"job_uuid": self.job_uuid}))
