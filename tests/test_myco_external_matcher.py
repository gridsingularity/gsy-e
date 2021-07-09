import json
from unittest.mock import MagicMock, patch

import pytest
from pendulum import now

import d3a.models.market.market_redis_connection
from d3a.d3a_core.exceptions import InvalidBidOfferPairException, MycoValidationException
from d3a.models.market import Offer, Bid
from d3a.models.market.two_sided import TwoSidedMarket
from d3a.models.myco_matcher import ExternalMatcher

d3a.models.myco_matcher.external_matcher.BlockingCommunicator = MagicMock
d3a.models.myco_matcher.external_matcher.ResettableCommunicator = MagicMock


class TestMycoExternalMatcher:

    @classmethod
    def setup_class(cls):
        cls.matcher = ExternalMatcher()
        cls.market = TwoSidedMarket(time_slot=now())
        cls.matcher.markets_mapping = {cls.market.id: cls.market}
        cls.redis_connection = d3a.models.myco_matcher.external_matcher.ResettableCommunicator
        assert cls.matcher.simulation_id == d3a.constants.COLLABORATION_ID
        cls.channel_prefix = f"external-myco/{d3a.constants.COLLABORATION_ID}/"
        cls.response_channel = f"{cls.channel_prefix}response"
        cls.events_channel = f"{cls.response_channel}/events/"

    def setup_method(self, method):
        self.matcher.myco_ext_conn.publish_json.reset_mock()

    def _populate_market_bids_offers(self):
        self.market.offers = {"id1": Offer("id1", now(), 3, 3, "seller", 3),
                              "id2": Offer("id2", now(), 0.5, 1, "seller", 0.5)}

        self.market.bids = {"id3": Bid("id3", now(), 1, 1, "buyer", 1),
                            "id4": Bid("id4", now(), 0.5, 1, "buyer", 1)}

    def test_subscribes_to_redis_channels(self):
        self.matcher.myco_ext_conn.sub_to_multiple_channels.assert_called_once_with(
            {
                "external-myco/get-simulation-id": self.matcher.publish_simulation_id,
                f"{self.channel_prefix}offers-bids/": self.matcher.publish_offers_bids,
                f"{self.channel_prefix}post-recommendations/":
                    self.matcher.match_recommendations
            }
        )

    def test_publish_simulation_id(self):
        channel = "external-myco/get-simulation-id/response"
        self.matcher.publish_simulation_id({})
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            channel, {"simulation_id": self.matcher.simulation_id})

    def test_publish_event_tick_myco(self):
        data = {"event": "tick"}
        self.matcher.publish_event_tick_myco()
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            self.events_channel, data)

    def test_publish_event_market_myco(self):
        data = {"event": "market"}
        self.matcher.publish_event_market_myco()
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            self.events_channel, data)

    def test_publish_event_finish_myco(self):
        data = {"event": "finish"}
        self.matcher.publish_event_finish_myco()
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            self.events_channel, data)

    def test_update_area_uuid_markets_mapping(self):
        mapping_dict = {"areax": [self.market]}
        self.matcher.area_uuid_markets_mapping = {}
        self.matcher.update_area_uuid_markets_mapping({"areax": [self.market]})
        assert mapping_dict == self.matcher.area_uuid_markets_mapping

    def test_get_bids_offers(self):
        self._populate_market_bids_offers()
        bids, offers = self.market.open_bids_and_offers
        expected_bids_list = list(bid.serializable_dict() for bid in bids.values())
        expected_offers_list = list(offer.serializable_dict() for offer in offers.values())

        actual_bids_list, actual_offers_list = self.matcher._get_bids_offers(self.market, {})
        assert (expected_bids_list, expected_offers_list) == (actual_bids_list, actual_offers_list)

        filters = {"energy_type": "Green"}
        # Offers which don't have attributes or of different energy type will be filtered out
        actual_bids_list, actual_offers_list = self.matcher._get_bids_offers(self.market, filters)
        assert (expected_bids_list, []) == (actual_bids_list, actual_offers_list)

        list(offers.values())[0].attributes = {"energy_type": "Green"}
        actual_bids_list, actual_offers_list = self.matcher._get_bids_offers(self.market, filters)
        bids, offers = self.market.open_bids_and_offers
        expected_offers_list = list(
            offer.serializable_dict() for offer in offers.values()
            if offer.attributes and offer.attributes.get("energy_type") == "Green")
        assert (expected_bids_list, expected_offers_list) == (actual_bids_list, actual_offers_list)

    @patch("d3a.models.myco_matcher.external_matcher.ExternalMatcher."
           "_get_bids_offers", MagicMock(return_value=([], [])))
    def test_publish_offers_bids(self):
        channel = f"{self.response_channel}/offers-bids/"
        payload = {
            "data": json.dumps({
                "filters": {}
            })
        }
        expected_data = {
            "event": "offers_bids_response",
            "bids_offers": {self.market.id: {"bids": [], "offers": []}}
        }
        self.matcher.update_area_uuid_markets_mapping({"area1": [self.market]})
        self.matcher.publish_offers_bids(payload)
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            channel, expected_data)
        self.matcher.myco_ext_conn.publish_json.reset_mock()

        # Apply market filter
        payload = {
            "data": json.dumps({
                "filters": {"markets": ["area2"]}
            })
        }
        expected_data = {
            "event": "offers_bids_response",
            "bids_offers": {}
        }
        self.matcher.publish_offers_bids(payload)
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            channel, expected_data)

    @patch("d3a.models.market.two_sided.TwoSidedMarket.validate_bid_offer_match",
           MagicMock())
    def test_get_validated_bid_offer_match_list(self):
        self._populate_market_bids_offers()
        records = [
            {
                "market_id": self.market.id,
                "bid": self.market.bids["id3"].serializable_dict(),
                "offer": self.market.offers["id1"].serializable_dict(),
                "trade_rate": 1,
                "selected_energy": 1},
            {
                "market_id": self.market.id,
                "bid": self.market.bids["id4"].serializable_dict(),
                "offer": self.market.offers["id2"].serializable_dict(),
                "trade_rate": 1,
                "selected_energy": 1}
        ]
        validated_records = self.matcher._get_validated_bid_offer_match_list(records)
        assert isinstance(validated_records, list)
        assert any(record["market_id"] == self.market.id for record in validated_records)
        assert len(list(filter(
            lambda record: record["market_id"] == self.market.id, validated_records))) == 2
        # should be called once for each record
        assert self.market.validate_bid_offer_match.call_count == 2

        # If the market is readonly, it should raise an exception
        self.market.readonly = True
        self.market.validate_bid_offer_match.reset_mock()
        with pytest.raises(MycoValidationException):
            validated_records = self.matcher._get_validated_bid_offer_match_list(records)
            assert validated_records is None
            # should not be called
            assert not self.market.validate_bid_offer_match.called

    @patch("d3a.models.myco_matcher.external_matcher.ExternalMatcher."
           "_get_validated_bid_offer_match_list", MagicMock())
    def test_match_recommendations(self):
        channel = f"{self.response_channel}/matched-recommendations/"
        expected_data = {"event": "match", "status": "success"}
        payload = {"data": json.dumps({})}
        # Empty recommendations list should pass
        self.matcher.match_recommendations(payload)
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            channel, expected_data)

        self.matcher.myco_ext_conn.publish_json.reset_mock()
        self.matcher._get_validated_bid_offer_match_list.side_effect = InvalidBidOfferPairException
        self.matcher.match_recommendations(payload)
        expected_data = {"event": "match", "status": "fail", "message": "Validation Error"}
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            channel, expected_data)
