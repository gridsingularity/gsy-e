# pylint: disable=protected-access
from math import isclose
from unittest.mock import Mock
import pytest

from gsy_framework.constants_limits import GlobalConfig

from gsy_e.models.strategy.state.heatpump_tank_states.water_tank_state import (
    WaterTankState,
    TankParameters,
)

CURRENT_MARKET_SLOT = GlobalConfig.start_date
NEXT_MARKET_SLOT = CURRENT_MARKET_SLOT + GlobalConfig.slot_length


@pytest.fixture(name="water_tank")
def fixture_water_tank():
    water_tank = WaterTankState(
        tank_parameters=TankParameters(
            min_temp_C=30, max_temp_C=70, initial_temp_C=50, tank_volume_L=1000
        )
    )
    water_tank.init()
    yield water_tank


class TestWaterTankState:
    """"""

    def test_increase_tank_temp_from_heat_energy_correctly_updates_storage_temp_and_soc(
        self, water_tank
    ):
        # Given
        assert water_tank._soc.get(CURRENT_MARKET_SLOT) == 0.5
        assert water_tank._storage_temp_C.get(CURRENT_MARKET_SLOT) == 50
        # When
        water_tank.increase_tank_temp_from_heat_energy(
            heat_energy_kWh=5, time_slot=NEXT_MARKET_SLOT
        )
        # Then
        assert isclose(water_tank._soc.get(NEXT_MARKET_SLOT), 0.6077, abs_tol=0.001)
        assert isclose(water_tank._storage_temp_C.get(NEXT_MARKET_SLOT), 54.310, abs_tol=0.001)

    def test_decrease_tank_temp_from_heat_energy_correctly_updates_storage_temp_and_soc(
        self, water_tank
    ):
        # Given
        assert water_tank._soc.get(CURRENT_MARKET_SLOT) == 0.5
        assert water_tank._storage_temp_C.get(CURRENT_MARKET_SLOT) == 50
        # When
        water_tank.decrease_tank_temp_from_heat_energy(
            heat_energy_kWh=5, time_slot=NEXT_MARKET_SLOT
        )
        # Then
        assert isclose(water_tank._soc.get(NEXT_MARKET_SLOT), 0.392, abs_tol=0.001)
        assert isclose(water_tank._storage_temp_C.get(NEXT_MARKET_SLOT), 45.689, abs_tol=0.001)

    def test_no_charge_correctly_updates_storage_temp_and_soc(self, water_tank):
        # Given
        assert water_tank._soc.get(CURRENT_MARKET_SLOT) == 0.5
        assert water_tank._storage_temp_C.get(CURRENT_MARKET_SLOT) == 50
        # When
        water_tank.no_charge(time_slot=NEXT_MARKET_SLOT)
        # Then
        assert water_tank._soc.get(NEXT_MARKET_SLOT) == 0.5
        assert water_tank._storage_temp_C.get(NEXT_MARKET_SLOT) == 50

    @pytest.mark.parametrize("heat_demand_kJ, expected_energy_kJ", [[5000, 88520.0], [0, 83520.0]])
    def test_get_max_heat_energy_consumption_kJ_returns_the_correct_energy_value(
        self, water_tank, heat_demand_kJ, expected_energy_kJ
    ):
        # When
        max_energy = water_tank.get_max_heat_energy_consumption_kJ(
            CURRENT_MARKET_SLOT, heat_demand_kJ
        )
        # Then
        assert max_energy == expected_energy_kJ

    @pytest.mark.parametrize(
        "storage_temp_C, expected_energy_kJ",
        [[20, 46760], [25, 25880], [30, 5000], [40, 0], [80, 0]],
    )
    def test_get_min_heat_energy_consumption_kJ_returns_the_correct_energy_value(
        self, water_tank, storage_temp_C, expected_energy_kJ
    ):
        # Given
        water_tank.get_storage_temp_C = Mock(return_value=storage_temp_C)
        # When
        max_energy = water_tank.get_min_heat_energy_consumption_kJ(CURRENT_MARKET_SLOT, 5000)
        # Then
        assert isclose(max_energy, expected_energy_kJ, abs_tol=0.1)

    def test_current_tank_temperature(self, water_tank):
        water_tank._storage_temp_C = {CURRENT_MARKET_SLOT: 20}
        assert water_tank.current_tank_temperature(CURRENT_MARKET_SLOT) == 20

    def test_init(self):
        # Given
        water_tank = WaterTankState(
            tank_parameters=TankParameters(
                min_temp_C=30, max_temp_C=70, initial_temp_C=50, tank_volume_L=1000
            )
        )
        assert water_tank._soc == {}
        # When
        water_tank.init()
        # Then
        assert water_tank._soc == {CURRENT_MARKET_SLOT: 0.5}

    def test_get_results_dict(self, water_tank):
        assert water_tank.get_results_dict(CURRENT_MARKET_SLOT) == {
            "storage_temp_C": 50,
            "soc": 50,
            "type": "WATER",
        }
