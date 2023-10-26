from unittest.mock import patch, Mock

from gsy_framework.constants_limits import GlobalConfig
from gsy_framework.enums import ConfigurationType

from gsy_e.gsy_e_core.rq_job_handler import launch_simulation_from_rq_job


class TestRqJobHandler:
    # pylint: disable=attribute-defined-outside-init

    def setup_method(self):
        self.original_config_type = GlobalConfig.CONFIG_TYPE

    def teardown_method(self):
        GlobalConfig.CONFIG_TYPE = self.original_config_type

    @staticmethod
    @patch("gsy_e.gsy_e_core.rq_job_handler.run_simulation", Mock())
    def test_config_type_is_correctly_set():
        assert GlobalConfig.CONFIG_TYPE == ConfigurationType.SIMULATION.value
        launch_simulation_from_rq_job(
            {"configuration_uuid": "config_uuid"},
            {"type": ConfigurationType.CANARY_NETWORK.value},
            None, {}, {}, "id"
        )
        assert GlobalConfig.CONFIG_TYPE == ConfigurationType.CANARY_NETWORK.value
