# pylint: disable=protected-access
import pytest
from gsy_framework.constants_limits import TIME_ZONE
from pendulum import duration, today

from gsy_e.models.strategy.state.heat_pump_state import HeatPumpState

CURRENT_MARKET_SLOT = today(tz=TIME_ZONE)


@pytest.fixture(name="hp_state")
def fixture_heatpump_state() -> HeatPumpState:
    return HeatPumpState(10, duration(minutes=15))


class TestHeatPumpState:

    @staticmethod
    def test_update_unmatched_demand_is_always_positive(hp_state):
        hp_state.update_unmatched_demand_kWh(CURRENT_MARKET_SLOT, -2)
        assert hp_state._unmatched_demand_kWh[CURRENT_MARKET_SLOT] == 0
        hp_state.update_unmatched_demand_kWh(CURRENT_MARKET_SLOT, 2)
        assert hp_state._unmatched_demand_kWh[CURRENT_MARKET_SLOT] == 2
