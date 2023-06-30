from unittest.mock import patch

import pytest

from gsy_e.models.strategy.scm.storage import SCMStorageStrategy


class TestScmStorage:

    @staticmethod
    @pytest.mark.parametrize("kwarg", [
        {"battery_capacity_kWh": 1},
        {"min_allowed_soc": 100},
        {"max_abs_battery_power_kW": 1},
    ])
    def test_area_reconfigure_event(kwarg):
        scm_storage = SCMStorageStrategy()
        state_key_mapping = {
            "battery_capacity_kWh": "capacity",
            "min_allowed_soc": "min_allowed_soc_ratio",
            "max_abs_battery_power_kW": "max_abs_battery_power_kW"
        }
        with patch("gsy_e.models.strategy.scm.storage.StorageValidator") as validator_mock:
            scm_storage.area_reconfigure_event(**kwarg)
            assert getattr(scm_storage._state, state_key_mapping[list(kwarg.keys())[0]]) == 1
            validator_mock.validate.assert_called_once()
