# pylint: disable=protected-access
import json
from unittest.mock import MagicMock, patch

import pytest
from pendulum import now

import gsy_e.constants
import gsy_e.models.market.market_redis_connection
from gsy_e.gsy_e_core.exceptions import MycoValidationException, InvalidBidOfferPairException
import gsy_e.gsy_e_core.redis_connections.redis_area_market_communicator
from gsy_e.models.market import Offer, Bid
from gsy_e.models.market.two_sided import TwoSidedMarket
from gsy_e.models.myco_matcher import MycoExternalMatcher
from gsy_e.models.myco_matcher.myco_external_matcher import MycoExternalMatcherValidator

gsy_e.gsy_e_core.redis_connections.redis_area_market_communicator.ResettableCommunicator = (
    MagicMock)


class TestMycoExternalMatcher:

    @classmethod
    def setup_method(cls):
        cls.matcher = MycoExternalMatcher()
        cls.market_id = "Area1"
        cls.market = TwoSidedMarket(time_slot=now())
        cls.matcher.area_markets_mapping = {
            f"{cls.market_id}-{cls.market.time_slot_str}": cls.market}

        assert cls.matcher.simulation_id == gsy_e.constants.CONFIGURATION_ID
        cls.channel_prefix = f"external-myco/{gsy_e.constants.CONFIGURATION_ID}/"
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
                f"{self.channel_prefix}offers-bids/":
                    self.matcher._publish_orders_message_buffer.append,
                f"{self.channel_prefix}recommendations/":
                    self.matcher._populate_recommendations
            }
        )

    def test_publish_simulation_id(self):
        channel = "external-myco/simulation-id/response/"
        self.matcher.publish_simulation_id({})
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            channel, {"simulation_id": self.matcher.simulation_id})

    def test_event_tick(self):
        data = {"event": "tick"}
        self.matcher._tick_counter.is_it_time_for_external_tick = MagicMock(return_value=True)
        self.matcher.event_tick(current_tick_in_slot=6)
        self.matcher._tick_counter.is_it_time_for_external_tick.assert_called_once_with(6)
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            self.events_channel, data)
        self.matcher._tick_counter.is_it_time_for_external_tick = MagicMock(return_value=False)
        self.matcher.event_tick(current_tick_in_slot=7)
        self.matcher._tick_counter.is_it_time_for_external_tick.assert_called_once_with(7)
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

    def test_get_orders(self):
        self._populate_market_bids_offers()
        expected_orders = self.market.orders_per_slot()

        actual_orders = self.matcher._get_orders(self.market, {})
        assert actual_orders == expected_orders

        filters = {"energy_type": "Green"}
        expected_orders[self.market.time_slot_str]["offers"] = []
        # Offers which don't have attributes or of different energy type will be filtered out
        actual_orders = self.matcher._get_orders(self.market, filters)
        assert actual_orders == expected_orders

        list(self.market.offers.values())[0].attributes = {"energy_type": "Green"}
        expected_orders = self.market.orders_per_slot()
        expected_orders[self.market.time_slot_str]["offers"].pop(1)
        actual_orders = self.matcher._get_orders(self.market, filters)
        assert actual_orders == expected_orders

    @patch("gsy_e.models.myco_matcher.myco_external_matcher.MycoExternalMatcher."
           "_get_orders", MagicMock(return_value=({})))
    def test_publish_offers_bids(self):
        channel = f"{self.channel_prefix}offers-bids/response/"
        payload = {
            "data": json.dumps({
                "filters": {}
            })
        }
        expected_data = {
            "event": "offers_bids_response",
            "bids_offers": {"area1": {}}
        }
        self.matcher.update_area_uuid_markets_mapping({"area1": {"markets": [self.market]}})
        self.matcher._publish_orders_message_buffer = [payload]
        self.matcher._publish_orders()
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
        self.matcher._publish_orders_message_buffer = [payload]
        self.matcher._publish_orders()
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            channel, expected_data)

    @patch("gsy_e.models.myco_matcher.myco_external_matcher.MycoExternalMatcherValidator."
           "validate_and_report")
    @patch("gsy_e.models.myco_matcher.myco_external_matcher.TwoSidedMarket."
           "match_recommendations", return_value=True)
    def test_match_recommendations(
            self, mock_market_match_recommendations, mock_validate_and_report):
        channel = f"{self.channel_prefix}recommendations/response/"
        payload = {"data": json.dumps({})}
        # Empty recommendations list should pass
        mock_validate_and_report.return_value = {
            "status": "success", "recommendations": []}
        self.matcher._populate_recommendations(payload)
        self.matcher.match_recommendations()
        assert not self.matcher._recommendations
        mock_market_match_recommendations.assert_not_called()
        self.matcher.myco_ext_conn.publish_json.assert_not_called()

        self.matcher.myco_ext_conn.publish_json.reset_mock()
        mock_validate_and_report.return_value = {
            "status": "fail",
            "message": "Validation Error, matching will be skipped: Invalid Bid Offer Pair",
            "recommendations": []}
        payload = {"data": json.dumps({"recommended_matches": [{}, {}]})}
        self.matcher._populate_recommendations(payload)
        self.matcher.match_recommendations()
        assert not self.matcher._recommendations
        expected_data = {
            "event": "match", "status": "fail",
            "recommendations": [],
            "message": "Validation Error, matching will be skipped: Invalid Bid Offer Pair"}
        mock_market_match_recommendations.assert_not_called()
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            channel, expected_data)

        self.matcher.myco_ext_conn.publish_json.reset_mock()
        mock_validate_and_report.return_value = {
            "status": "success",
            "recommendations": [{"status": "success",
                                 "market_id": self.market_id,
                                 "time_slot": self.market.time_slot_str}]}
        self.matcher._populate_recommendations(payload)
        self.matcher.match_recommendations()
        assert not self.matcher._recommendations
        expected_data = {
            "event": "match", "status": "success",
            "recommendations": [{"market_id": self.market_id,
                                 "status": "success",
                                 "time_slot": self.market.time_slot_str}]}
        assert mock_market_match_recommendations.call_count == 1
        self.matcher.myco_ext_conn.publish_json.assert_called_once_with(
            channel, expected_data)


class TestMycoExternalMatcherValidator:
    @staticmethod
    @patch("gsy_e.models.myco_matcher.myco_external_matcher.MycoExternalMatcherValidator."
           "_validate")
    def test_validate_and_report(mock_validate):
        recommendations = []
        expected_data = {"status": "success", "recommendations": []}
        assert MycoExternalMatcherValidator.validate_and_report(
            None, recommendations) == expected_data

        recommendations = [{
                "market_id": "market",
                "time_slot": "2021-10-06T12:00",
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

        mock_validate.side_effect = InvalidBidOfferPairException
        expected_data = {"status": "success",
                         "recommendations": [{
                             "market_id": "market",
                             "time_slot": "2021-10-06T12:00",
                             "bids": [],
                             "offers": [],
                             "trade_rate": 1,
                             "selected_energy": 1,
                             "status": "fail",
                             "message": ""
                            }]}
        assert MycoExternalMatcherValidator.validate_and_report(
            None, recommendations) == expected_data

    @staticmethod
    @patch("gsy_e.models.myco_matcher.myco_external_matcher.BidOfferMatch.is_valid_dict")
    def test_validate_valid_dict(mock_is_valid_dict):
        mock_is_valid_dict.return_value = True
        assert MycoExternalMatcherValidator._validate_valid_dict(None, {}) is None

        mock_is_valid_dict.return_value = False
        with pytest.raises(MycoValidationException):
            MycoExternalMatcherValidator._validate_valid_dict(None, {})

    @staticmethod
    @patch("gsy_e.models.myco_matcher.myco_external_matcher.MycoExternalMatcher")
    def test_validate_market_exists(mock_myco_external_matcher):
        market = MagicMock()
        market.time_slot_str = "2021-10-06T12:00"
        mock_myco_external_matcher.area_markets_mapping = {"market-2021-10-06T12:00": market}
        recommendation = {"market_id": "market", "time_slot": "2021-10-06T12:00"}
        assert MycoExternalMatcherValidator._validate_market_exists(
            mock_myco_external_matcher, recommendation) is None

        mock_myco_external_matcher.area_markets_mapping = {}
        with pytest.raises(MycoValidationException):
            MycoExternalMatcherValidator._validate_market_exists(
                mock_myco_external_matcher, recommendation)

    @staticmethod
    @patch("gsy_e.models.myco_matcher.myco_external_matcher.MycoExternalMatcher")
    def test_validate_orders_exist_in_market(mock_myco_external_matcher):
        market = MagicMock()
        market.time_slot_str = "2021-10-06T12:00"
        market.offers = {"offer1": MagicMock()}
        market.bids = {"bid1": MagicMock()}
        mock_myco_external_matcher.area_markets_mapping = {"market-2021-10-06T12:00": market}
        recommendation = {
            "market_id": "market",
            "time_slot": "2021-10-06T12:00",
            "offer": {"id": "offer1"}, "bid": {"id": "bid1"}}
        assert MycoExternalMatcherValidator._validate_orders_exist_in_market(
            mock_myco_external_matcher, recommendation) is None

        recommendation["offer"] = {"id": "offer2"}
        with pytest.raises(InvalidBidOfferPairException):
            MycoExternalMatcherValidator._validate_orders_exist_in_market(
                mock_myco_external_matcher, recommendation
            )
