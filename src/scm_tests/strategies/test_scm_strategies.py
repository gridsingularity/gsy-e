import uuid
from unittest.mock import patch

import pytest

from scm.strategies.heat_pump import ScmHeatPumpStrategy
from scm.strategies.load import SCMLoadProfileStrategy
from scm.strategies.pv import SCMPVUserProfile
from scm.strategies.smart_meter import SCMSmartMeterStrategy
from scm.strategies.storage import SCMStorageStrategy


class TestScmStrategies:

    @staticmethod
    @patch("gsy_framework.constants_limits.GlobalConfig.is_canary_network", lambda: True)
    @pytest.mark.parametrize(
        "strategy_class, measurement_key, forecast_key",
        [
            [
                SCMStorageStrategy,
                "prosumption_kWh_measurement_uuid",
                "prosumption_kWh_profile_uuid",
            ],
            [SCMLoadProfileStrategy, "daily_load_measurement_uuid", "daily_load_profile_uuid"],
            [SCMPVUserProfile, "power_measurement_uuid", "power_profile_uuid"],
            [SCMSmartMeterStrategy, "smart_meter_measurement_uuid", "smart_meter_profile_uuid"],
            [
                ScmHeatPumpStrategy,
                "consumption_kWh_measurement_uuid",
                "consumption_kWh_profile_uuid",
            ],
        ],
    )
    def test_deserialize_args(strategy_class, measurement_key, forecast_key):
        constructor_args = {measurement_key: str(uuid.uuid4()), forecast_key: str(uuid.uuid4())}
        updated_constructor_args = strategy_class.deserialize_args(constructor_args)
        assert updated_constructor_args[forecast_key] == constructor_args[measurement_key]
