from datetime import date

from unittest.mock import patch, Mock

import pytest
from pendulum import duration, now, datetime

from gsy_framework.constants_limits import GlobalConfig, ConstSettings
from gsy_framework.enums import ConfigurationType, CoefficientAlgorithm

import gsy_e.constants
from gsy_e.gsy_e_core.rq_job_handler import launch_simulation_from_rq_job


class TestRqJobHandler:
    # pylint: disable=attribute-defined-outside-init

    def setup_method(self):
        self.original_config_type = GlobalConfig.CONFIG_TYPE
        self.original_external_connection_web = gsy_e.constants.EXTERNAL_CONNECTION_WEB
        self.original_run_in_realtime = gsy_e.constants.RUN_IN_REALTIME
        self.original_sertsvr = gsy_e.constants.SEND_EVENTS_RESPONSES_TO_SDK_VIA_RQ
        self.original_connect_to_profiles_db = gsy_e.constants.CONNECT_TO_PROFILES_DB
        self.original_config_id = gsy_e.constants.CONFIGURATION_ID
        self.original_start_date = GlobalConfig.start_date

    def teardown_method(self):
        GlobalConfig.CONFIG_TYPE = self.original_config_type
        GlobalConfig.start_date = self.original_start_date
        gsy_e.constants.EXTERNAL_CONNECTION_WEB = self.original_external_connection_web
        gsy_e.constants.RUN_IN_REALTIME = self.original_run_in_realtime
        gsy_e.constants.SEND_EVENTS_RESPONSES_TO_SDK_VIA_RQ = self.original_sertsvr
        gsy_e.constants.CONNECT_TO_PROFILES_DB = self.original_connect_to_profiles_db
        gsy_e.constants.CONFIGURATION_ID = self.original_config_id
        ConstSettings.SCMSettings.MARKET_ALGORITHM = CoefficientAlgorithm.STATIC.value
        ConstSettings.SCMSettings.INTRACOMMUNITY_BASE_RATE_EUR = None
        ConstSettings.SCMSettings.GRID_FEES_REDUCTION = 0.28
        gsy_e.constants.EXTERNAL_CONNECTION_WEB = False
        gsy_e.constants.RUN_IN_REALTIME = False
        ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = False
        ConstSettings.MASettings.MARKET_TYPE = 1
        ConstSettings.MASettings.BID_OFFER_MATCH_TYPE = 1

    @staticmethod
    @patch("gsy_e.gsy_e_core.rq_job_handler.run_simulation", Mock())
    @pytest.mark.parametrize("config_type", [
        ConfigurationType.COLLABORATION, ConfigurationType.CANARY_NETWORK, ConfigurationType.B2B])
    def test_config_type_is_correctly_set(config_type):
        assert GlobalConfig.CONFIG_TYPE == ConfigurationType.SIMULATION.value
        settings = {"type": config_type.value}
        scenario = {"configuration_uuid": "config_uuid"}
        with patch("gsy_e.gsy_e_core.rq_job_handler._adapt_settings", Mock(return_value=settings)):
            launch_simulation_from_rq_job(scenario, settings, None, {}, {}, "id")
        assert GlobalConfig.CONFIG_TYPE == config_type.value
        assert gsy_e.constants.EXTERNAL_CONNECTION_WEB is True
        if config_type == ConfigurationType.CANARY_NETWORK:
            assert gsy_e.constants.RUN_IN_REALTIME is True
        if config_type == ConfigurationType.B2B:
            assert ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS is True
            assert ConstSettings.ForwardMarketSettings.FULLY_AUTO_TRADING is False

    @staticmethod
    @patch("gsy_e.gsy_e_core.rq_job_handler.run_simulation", Mock())
    def test_scm_settings_are_correctly_set():
        settings = {
            "type": ConfigurationType.CANARY_NETWORK.value,
            "spot_market_type": 3,
            "bid_offer_match_algo": 2,
            "scm": {
                "coefficient_algorithm": 3,
                "grid_fees_reduction": 0.45,
                "intracommunity_rate_base_eur": 12
            }
        }
        scenario = {"configuration_uuid": "config_uuid"}
        launch_simulation_from_rq_job(scenario, settings, None, {}, {}, "id")
        assert (ConstSettings.SCMSettings.MARKET_ALGORITHM ==
                CoefficientAlgorithm.NO_COMMUNITY_SELF_CONSUMPTION.value)
        assert ConstSettings.SCMSettings.INTRACOMMUNITY_BASE_RATE_EUR == 12
        assert ConstSettings.SCMSettings.GRID_FEES_REDUCTION == 0.45
        assert ConstSettings.MASettings.MARKET_TYPE == 3
        assert ConstSettings.MASettings.BID_OFFER_MATCH_TYPE == 2

    @staticmethod
    @patch("gsy_e.gsy_e_core.rq_job_handler.run_simulation")
    def test_past_market_slots_handles_settings_correctly(run_sim_mock: Mock):
        settings = {
            "type": ConfigurationType.CANARY_NETWORK.value,
            "start_date": date(2023, 1, 1),
            "slot_length": duration(minutes=30),
            "tick_length": duration(seconds=20),
            "advanced_settings": '''{
                "BalancingSettings": {"SPOT_TRADE_RATIO": 0.99}
            }'''
        }
        scenario = {"configuration_uuid": "config_uuid"}
        launch_simulation_from_rq_job(scenario, settings, None, {}, {"scm_past_slots": True}, "id")
        assert run_sim_mock.call_count == 2
        config = run_sim_mock.call_args_list[0][1]["simulation_config"]
        assert config.slot_length == duration(minutes=30)
        assert config.tick_length == duration(seconds=20)
        assert config.start_date == datetime(2023, 1, 1)
        expected_end_date = now(tz=gsy_e.constants.TIME_ZONE).subtract(
            days=gsy_e.constants.SCM_CN_DAYS_OF_DELAY).add(hours=4)
        assert (config.end_date.replace(second=0, microsecond=0) ==
                expected_end_date.replace(second=0, microsecond=0))
        assert config.sim_duration == config.end_date - config.start_date
        assert ConstSettings.BalancingSettings.SPOT_TRADE_RATIO == 0.99

    @staticmethod
    @patch("gsy_e.gsy_e_core.rq_job_handler.run_simulation",
           Mock(side_effect=Exception("Fake Error")))
    @patch("gsy_e.gsy_e_core.redis_connections.simulation.publish_job_error_output")
    def test_error_during_launch_simulation_published_via_redis(publish_job_error_mock):
        settings = {
            "type": ConfigurationType.CANARY_NETWORK.value,
        }
        scenario = {"configuration_uuid": "config_uuid"}
        with pytest.raises(Exception):
            launch_simulation_from_rq_job(scenario, settings, None, {}, {}, "id")
        assert publish_job_error_mock.call_count == 1
        assert publish_job_error_mock.call_args_list[0][0][0] == "id"
        assert "Fake Error" in publish_job_error_mock.call_args_list[0][0][1]

    @staticmethod
    def test_launch_simulation_raises_if_config_uuid_not_provided():
        settings = {
            "type": ConfigurationType.CANARY_NETWORK.value,
        }
        scenario = {}
        with pytest.raises(Exception):
            launch_simulation_from_rq_job(scenario, settings, None, {}, {}, "id")
