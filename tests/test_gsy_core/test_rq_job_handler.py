from unittest.mock import patch, Mock

from gsy_framework.constants_limits import GlobalConfig
from gsy_framework.enums import ConfigurationType

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

    def teardown_method(self):
        GlobalConfig.CONFIG_TYPE = self.original_config_type
        gsy_e.constants.EXTERNAL_CONNECTION_WEB = self.original_external_connection_web
        gsy_e.constants.RUN_IN_REALTIME = self.original_run_in_realtime
        gsy_e.constants.SEND_EVENTS_RESPONSES_TO_SDK_VIA_RQ = self.original_sertsvr
        gsy_e.constants.CONNECT_TO_PROFILES_DB = self.original_connect_to_profiles_db
        gsy_e.constants.CONFIGURATION_ID = self.original_config_id

    @staticmethod
    @patch("gsy_e.gsy_e_core.rq_job_handler.run_simulation", Mock())
    def test_config_type_is_correctly_set():
        assert GlobalConfig.CONFIG_TYPE == ConfigurationType.SIMULATION.value
        settings = {"type": ConfigurationType.CANARY_NETWORK.value}
        scenario = {"configuration_uuid": "config_uuid"}
        with patch("gsy_e.gsy_e_core.rq_job_handler._adapt_settings", Mock(return_value=settings)):
            launch_simulation_from_rq_job(scenario, settings, None, {}, {}, "id")
        assert GlobalConfig.CONFIG_TYPE == ConfigurationType.CANARY_NETWORK.value
