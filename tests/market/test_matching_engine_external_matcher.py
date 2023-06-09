# pylint: disable=protected-access
import json
from unittest.mock import MagicMock, patch

import pytest
from gsy_framework.data_classes import Offer, Bid, TraderDetails
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.redis_channels import MatchingEngineChannels
from pendulum import now

import gsy_e.constants
import gsy_e.gsy_e_core.redis_connections.area_market
import gsy_e.models.market.market_redis_connection
from gsy_e.gsy_e_core.exceptions import (InvalidBidOfferPairException,
                                         MatchingEngineValidationException)
from gsy_e.models.market.two_sided import TwoSidedMarket
from gsy_e.models.matching_engine_matcher import MatchingEngineExternalMatcher
from gsy_e.models.matching_engine_matcher.matching_engine_external_matcher import \
    MatchingEngineExternalMatcherValidator

gsy_e.gsy_e_core.redis_connections.area_market.ResettableCommunicator = MagicMock


class TestMatchingEngineExternalMatcher:

    @classmethod
    def setup_method(cls):
        cls.matcher = MatchingEngineExternalMatcher()
        cls.market_id = "Area1"
        cls.market = TwoSidedMarket(time_slot=now())
        cls.matcher.area_markets_mapping = {
            f"{cls.market_id}-{cls.market.time_slot_str}": cls.market}

        assert cls.matcher.simulation_id == gsy_e.constants.CONFIGURATION_ID
        cls.channel_prefix = f"external-matching-engine/{gsy_e.constants.CONFIGURATION_ID}/"
        cls.events_channel = f"{cls.channel_prefix}events/"

    def _populate_market_bids_offers(self):
        self.market.offers = {"id1": Offer("id1", now(), 3, 3, TraderDetails("seller", ""), 3),
                              "id2": Offer("id2", now(), 0.5, 1, TraderDetails("seller", ""), 0.5)}

        self.market.bids = {"id3": Bid("id3", now(), 1, 1, TraderDetails("buyer", ""), 1),
                            "id4": Bid("id4", now(), 0.5, 1, TraderDetails("buyer", ""), 1)}

    def test_subscribes_to_redis_channels(self):
        channel_names = MatchingEngineChannels(gsy_e.constants.CONFIGURATION_ID)
        self.matcher.matching_engine_ext_conn.sub_to_multiple_channels.assert_called_once_with(
            {channel_names.simulation_id: self.matcher.publish_simulation_id,
             channel_names.offers_bids: self.matcher._publish_orders_message_buffer.append,
             channel_names.recommendations: self.matcher._populate_recommendations}
        )

    def test_publish_simulation_id(self):
        self.matcher.publish_simulation_id({})
        self.matcher.matching_engine_ext_conn.publish_json.assert_called_once_with(
            MatchingEngineChannels(gsy_e.constants.CONFIGURATION_ID).simulation_id_response,
            {"simulation_id": self.matcher.simulation_id})

    def test_event_tick(self):
        data = {"event": "tick", "markets_info": {self.market.id: self.market.info}}
        self.matcher._tick_counter.is_it_time_for_external_tick = MagicMock(return_value=True)
        self.matcher.event_tick(current_tick_in_slot=6)

        self.matcher._tick_counter.is_it_time_for_external_tick.assert_called_once_with(6)
        self.matcher.matching_engine_ext_conn.publish_json.assert_called_once_with(
            self.events_channel, data)

        self.matcher._tick_counter.is_it_time_for_external_tick = MagicMock(return_value=False)
        self.matcher.event_tick(current_tick_in_slot=7)
        self.matcher._tick_counter.is_it_time_for_external_tick.assert_called_once_with(7)
        # should still be == 1 as the above won't trigger the publish_json method
        assert self.matcher.matching_engine_ext_conn.publish_json.call_count == 1

    def test_event_market_cycle(self):
        assert self.matcher.area_markets_mapping
        data = {"event": "market_cycle"}
        self.matcher.event_market_cycle()
        # Market cycle event should clear the markets cache
        assert not self.matcher.area_markets_mapping
        self.matcher.matching_engine_ext_conn.publish_json.assert_called_once_with(
            self.events_channel, data)

    def test_event_finish(self):
        data = {"event": "finish"}
        self.matcher.event_finish()
        self.matcher.matching_engine_ext_conn.publish_json.assert_called_once_with(
            self.events_channel, data)

    def test_update_area_uuid_markets_mapping(self):
        mapping_dict = {"areax": {"markets": [self.market]}}
        self.matcher.area_uuid_markets_mapping = {}
        self.matcher.update_area_uuid_markets_mapping({"areax": {"markets": [self.market]}})
        assert mapping_dict == self.matcher.area_uuid_markets_mapping

    @pytest.mark.skip("Attributes / requirements feature disabled.")
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

    @patch("gsy_e.models.matching_engine_matcher.matching_engine_external_matcher."
           "MatchingEngineExternalMatcher._get_orders", MagicMock(return_value=({})))
    def test_publish_offers_bids(self):
        payload = {
            "data": json.dumps({
                "filters": {}
            })
        }
        expected_data = {
            "event": "offers_bids_response",
            "bids_offers": {"area1": {}}
        }
        self.matcher.update_area_uuid_markets_mapping(
            {"area1": {AvailableMarketTypes.SPOT: [self.market]}})
        self.matcher._publish_orders_message_buffer = [payload]
        self.matcher._publish_orders()
        self.matcher.matching_engine_ext_conn.publish_json.assert_called_once_with(
            MatchingEngineChannels(gsy_e.constants.CONFIGURATION_ID).response, expected_data)
        self.matcher.matching_engine_ext_conn.publish_json.reset_mock()

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
        self.matcher.matching_engine_ext_conn.publish_json.assert_called_once_with(
            MatchingEngineChannels(gsy_e.constants.CONFIGURATION_ID).response, expected_data)

    @patch("gsy_e.models.matching_engine_matcher.matching_engine_external_matcher."
           "MatchingEngineExternalMatcherValidator.validate_and_report")
    @patch("gsy_e.models.matching_engine_matcher.matching_engine_external_matcher."
           "TwoSidedMarket.match_recommendations", return_value=True)
    def test_match_recommendations(
            self, mock_market_match_recommendations, mock_validate_and_report):
        payload = {"data": json.dumps({})}
        # Empty recommendations list should pass
        mock_validate_and_report.return_value = {
            "status": "success", "recommendations": []}
        self.matcher._populate_recommendations(payload)
        self.matcher.match_recommendations()
        assert not self.matcher._recommendations
        mock_market_match_recommendations.assert_not_called()
        self.matcher.matching_engine_ext_conn.publish_json.assert_not_called()

        self.matcher.matching_engine_ext_conn.publish_json.reset_mock()
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
        self.matcher.matching_engine_ext_conn.publish_json.assert_called_once_with(
            MatchingEngineChannels(gsy_e.constants.CONFIGURATION_ID).response, expected_data)

        self.matcher.matching_engine_ext_conn.publish_json.reset_mock()
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
        self.matcher.matching_engine_ext_conn.publish_json.assert_called_once_with(
            MatchingEngineChannels(gsy_e.constants.CONFIGURATION_ID).response, expected_data)


class TestMatchingEngineExternalMatcherValidator:
    @staticmethod
    @patch("gsy_e.models.matching_engine_matcher.matching_engine_external_matcher."
           "MatchingEngineExternalMatcherValidator._validate")
    def test_validate_and_report(mock_validate):
        recommendations = []
        expected_data = {"status": "success", "recommendations": []}
        assert MatchingEngineExternalMatcherValidator.validate_and_report(
            None, recommendations) == expected_data

        recommendations = [{
                "market_id": "market",
                "time_slot": "2021-10-06T12:00",
                "bids": [],
                "offers": [],
                "trade_rate": 1,
                "selected_energy": 1}]
        mock_validate.side_effect = MatchingEngineExternalMatcherValidator.BLOCKING_EXCEPTIONS[0]
        expected_data = {"status": "fail",
                         "message": "Validation Error, matching will be skipped: ",
                         "recommendations": []}
        assert MatchingEngineExternalMatcherValidator.validate_and_report(
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
        assert MatchingEngineExternalMatcherValidator.validate_and_report(
            None, recommendations) == expected_data

    # pylint: disable=line-too-long
    @staticmethod
    @patch("gsy_e.models.matching_engine_matcher.matching_engine_external_matcher."
           "BidOfferMatch.is_valid_dict")
    def test_validate_valid_dict(mock_is_valid_dict):
        mock_is_valid_dict.return_value = True
        assert MatchingEngineExternalMatcherValidator._validate_valid_dict(None, {}) is None

        mock_is_valid_dict.return_value = False
        with pytest.raises(MatchingEngineValidationException):
            MatchingEngineExternalMatcherValidator._validate_valid_dict(None, {})

    # pylint: disable=line-too-long
    @staticmethod
    @patch("gsy_e.models.matching_engine_matcher.matching_engine_external_matcher."
           "MatchingEngineExternalMatcher")
    def test_validate_market_exists(mock_matching_engine_external_matcher):
        market = MagicMock()
        market.time_slot_str = "2021-10-06T12:00"
        mock_matching_engine_external_matcher.area_markets_mapping = \
            {"market-2021-10-06T12:00": market}
        recommendation = {"market_id": "market", "time_slot": "2021-10-06T12:00"}
        assert MatchingEngineExternalMatcherValidator._validate_market_exists(
            mock_matching_engine_external_matcher, recommendation) is None

        mock_matching_engine_external_matcher.area_markets_mapping = {}
        with pytest.raises(MatchingEngineValidationException):
            MatchingEngineExternalMatcherValidator._validate_market_exists(
                mock_matching_engine_external_matcher, recommendation)

    # pylint: disable=line-too-long
    @staticmethod
    @patch("gsy_e.models.matching_engine_matcher.matching_engine_external_matcher."
           "MatchingEngineExternalMatcher")
    def test_validate_orders_exist_in_market(mock_matching_engine_external_matcher):
        market = MagicMock()
        market.time_slot_str = "2021-10-06T12:00"
        market.offers = {"offer1": MagicMock()}
        market.bids = {"bid1": MagicMock()}
        mock_matching_engine_external_matcher.area_markets_mapping = \
            {"market-2021-10-06T12:00": market}
        recommendation = {
            "market_id": "market",
            "time_slot": "2021-10-06T12:00",
            "offer": {"id": "offer1"}, "bid": {"id": "bid1"}}
        assert MatchingEngineExternalMatcherValidator._validate_orders_exist_in_market(
            mock_matching_engine_external_matcher, recommendation) is None

        recommendation["offer"] = {"id": "offer2"}
        with pytest.raises(InvalidBidOfferPairException):
            MatchingEngineExternalMatcherValidator._validate_orders_exist_in_market(
                mock_matching_engine_external_matcher, recommendation
            )
