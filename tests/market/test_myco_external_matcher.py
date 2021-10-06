import json
from unittest.mock import MagicMock, patch

import pytest
from pendulum import now

import d3a.models.market.market_redis_connection
from d3a.d3a_core.exceptions import MycoValidationException, InvalidBidOfferPairException
from d3a.models.market import Offer, Bid
from d3a.models.market.two_sided import TwoSidedMarket
from d3a.models.myco_matcher import MycoExternalMatcher
from d3a.models.myco_matcher.myco_external_matcher import MycoExternalMatcherValidator

d3a.models.myco_matcher.myco_external_matcher.BlockingCommunicator = MagicMock
d3a.models.myco_matcher.myco_external_matcher.ResettableCommunicator = MagicMock


class TestMycoExternalMatcher:

    @classmethod
    def setup_method(cls):
        cls.matcher = MycoExternalMatcher()
        cls.market = TwoSidedMarket(time_slot=now())
        cls.matcher.area_markets_mapping = {
            f"Area1-{cls.market.time_slot_str}": cls.market}
        cls.redis_connection = d3a.models.myco_matcher.myco_external_matcher.ResettableCommunicator
        assert cls.matcher.simulation_id == d3a.constants.CONFIGURATION_ID
        cls.channel_prefix = f"external-myco/{d3a.constants.CONFIGURATION_ID}/"
        cls.events_channel = f"{cls.channel_prefix}events/"

    def _populate_market_bids_offers(self):
        self.market.offers = {"id1": Offer("id1", now(), 3, 3, "seller", 3),
                              "id2": Offer("id2", now(), 0.5, 1, "seller", 0.5)}

        self.market.bids = {"id3": Bid("id3", now(), 1, 1, "buyer", 1),
                            "id4": Bid("id4", now(), 0.5, 1, "buyer", 1)}

    def test_subscribes_to_redis_channels(self):
        self.matcher.myco_ext_conn.sub_to_multiple_channels.assert_called_once_with(
            {
                "external-myco/simulation-id/": self.matcher.publish_simulation_id,
                f"{self.channel_prefix}offers-bids/": self.matcher.publish_offers_bids,
                f"{self.channel_prefix}recommendations/":
                    self.matcher.match_recommendations
            }
        )

    def test_publish_simulation_id(self):
        channel = "external-myco/simulation-id/response/"
        self.matcher.publish_simulation_id({})
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            channel, {"simulation_id": self.matcher.simulation_id})

    def test_event_tick(self):
        data = {"event": "tick"}
        self.matcher.event_tick()
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            self.events_channel, data)

        self.matcher.event_tick(is_it_time_for_external_tick=False)
        # should still be == 1 as the above won't trigger the publish_json method
        assert self.matcher.myco_ext_conn.publish_json.call_count == 1

    def test_event_market_cycle(self):
        assert self.matcher.area_markets_mapping
        data = {"event": "market_cycle"}
        self.matcher.event_market_cycle()
        # Market cycle event should clear the markets cache
        assert not self.matcher.area_markets_mapping
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            self.events_channel, data)

    def test_event_finish(self):
        data = {"event": "finish"}
        self.matcher.event_finish()
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            self.events_channel, data)

    def test_update_area_uuid_markets_mapping(self):
        mapping_dict = {"areax": {"markets": [self.market]}}
        self.matcher.area_uuid_markets_mapping = {}
        self.matcher.update_area_uuid_markets_mapping({"areax": {"markets": [self.market]}})
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

    @patch("d3a.models.myco_matcher.myco_external_matcher.MycoExternalMatcher."
           "_get_bids_offers", MagicMock(return_value=([], [])))
    def test_publish_offers_bids(self):
        channel = f"{self.channel_prefix}offers-bids/response/"
        payload = {
            "data": json.dumps({
                "filters": {}
            })
        }
        expected_data = {
            "event": "offers_bids_response",
            "bids_offers": {"area1": {self.market.time_slot_str: {"bids": [], "offers": []}}}
        }
        self.matcher.update_area_uuid_markets_mapping({"area1": {"markets": [self.market]}})
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

    @patch("d3a.models.myco_matcher.myco_external_matcher.MycoExternalMatcherValidator."
           "validate_and_report")
    @patch("d3a.models.myco_matcher.myco_external_matcher.TwoSidedMarket."
           "match_recommendations", return_value=None)
    def test_match_recommendations(
            self, mock_market_match_recommendations, mock_validate_and_report):
        channel = f"{self.channel_prefix}recommendations/response/"
        expected_data = {"event": "match", "status": "success", "recommendations": []}
        payload = {"data": json.dumps({})}
        # Empty recommendations list should pass
        mock_validate_and_report.return_value = {
            "status": "success", "recommendations": []}
        self.matcher.match_recommendations(payload)
        assert mock_market_match_recommendations.call_count == 0
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            channel, expected_data)

        self.matcher.myco_ext_conn.publish_json.reset_mock()
        mock_validate_and_report.return_value = {
            "status": "fail",
            "message": "Validation Error, matching will be skipped: Invalid Bid Offer Pair",
            "recommendations": []}
        self.matcher.match_recommendations(payload)
        expected_data = {
            "event": "match", "status": "fail",
            "recommendations": [],
            "message": "Validation Error, matching will be skipped: Invalid Bid Offer Pair"}
        assert mock_market_match_recommendations.call_count == 0
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            channel, expected_data)

        self.matcher.myco_ext_conn.publish_json.reset_mock()
        mock_validate_and_report.return_value = {
            "status": "success",
            "recommendations": [{"status": "success", "market_id": self.market.id}]}
        self.matcher.match_recommendations(payload)
        expected_data = {
            "event": "match", "status": "success",
            "recommendations": [{"market_id": self.market.id, "status": "success"}]}
        assert mock_market_match_recommendations.call_count == 1
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            channel, expected_data)


class TestMycoExternalMatcherValidator:
    @patch("d3a.models.myco_matcher.myco_external_matcher.MycoExternalMatcherValidator."
           "_validate")
    def test_validate_and_report(self, mock_validate):
        recommendations = []
        expected_data = {"status": "success", "recommendations": []}
        assert MycoExternalMatcherValidator.validate_and_report(
            None, recommendations) == expected_data

        recommendations = [{
                "market_id": "market",
                "bids": [],
                "offers": [],
                "trade_rate": 1,
                "selected_energy": 1}]
        mock_validate.side_effect = MycoExternalMatcherValidator.BLOCKING_EXCEPTIONS[0]
        expected_data = {"status": "fail",
                         "message": "Validation Error, matching will be skipped: ",
                         "recommendations": []}
        assert MycoExternalMatcherValidator.validate_and_report(
            None, recommendations) == expected_data

        mock_validate.side_effect = Exception
        expected_data = {"status": "success",
                         "recommendations": [{
                             "market_id": "market",
                             "bids": [],
                             "offers": [],
                             "trade_rate": 1,
                             "selected_energy": 1,
                             "status": "fail",
                             "message": ""
                            }]}
        assert MycoExternalMatcherValidator.validate_and_report(
            None, recommendations) == expected_data

    @patch("d3a.models.myco_matcher.myco_external_matcher.BidOfferMatch.is_valid_dict")
    def test_validate_valid_dict(self, mock_is_valid_dict):
        mock_is_valid_dict.return_value = True
        assert MycoExternalMatcherValidator.validate_valid_dict(None, {}) is None

        mock_is_valid_dict.return_value = False
        with pytest.raises(MycoValidationException):
            MycoExternalMatcherValidator.validate_valid_dict(None, {})

    @patch("d3a.models.myco_matcher.myco_external_matcher.MycoExternalMatcher")
    def test_validate_market_exists(self, mock_myco_external_matcher):
        mock_myco_external_matcher.markets_mapping = {"market": MagicMock()}
        recommendation = {"market_id": "market"}
        assert MycoExternalMatcherValidator.validate_market_exists(
            mock_myco_external_matcher, recommendation) is None

        mock_myco_external_matcher.markets_mapping = {}
        with pytest.raises(MycoValidationException):
            MycoExternalMatcherValidator.validate_market_exists(
                mock_myco_external_matcher, recommendation)

    @patch("d3a.models.myco_matcher.myco_external_matcher.MycoExternalMatcher")
    def test_validate_orders_exist_in_market(self, mock_myco_external_matcher):
        market = MagicMock()
        market.offers = {"offer1": MagicMock()}
        market.bids = {"bid1": MagicMock()}
        mock_myco_external_matcher.markets_mapping = {"market": market}
        recommendation = {
            "market_id": "market",
            "offers": [{"id": "offer1"}], "bids": [{"id": "bid1"}]}
        assert MycoExternalMatcherValidator.validate_orders_exist_in_market(
            mock_myco_external_matcher, recommendation) is None

        recommendation["offers"].append({"id": "offer2"})
        with pytest.raises(InvalidBidOfferPairException):
            MycoExternalMatcherValidator.validate_orders_exist_in_market(
                mock_myco_external_matcher, recommendation
            )
