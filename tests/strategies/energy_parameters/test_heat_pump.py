# pylint: disable=protected-access
from math import isclose
from unittest.mock import Mock, patch

import pytest
from gsy_framework.constants_limits import GlobalConfig, TIME_ZONE
from gsy_framework.utils import generate_market_slot_list
from pendulum import duration, today

from gsy_e.models.strategy.energy_parameters.heatpump.cop_models import COPModelType
from gsy_e.models.strategy.energy_parameters.heatpump.heat_pump import (
    HeatPumpEnergyParameters,
)
from gsy_e.models.strategy.energy_parameters.heatpump.tank_parameters import WaterTankParameters

CURRENT_MARKET_SLOT = today(tz=TIME_ZONE)


@pytest.fixture(name="energy_params")
def fixture_heatpump_energy_params() -> HeatPumpEnergyParameters:
    original_start_date = GlobalConfig.start_date
    original_sim_duration = GlobalConfig.sim_duration
    original_slot_length = GlobalConfig.slot_length
    GlobalConfig.start_date = CURRENT_MARKET_SLOT
    GlobalConfig.sim_duration = duration(days=1)
    GlobalConfig.slot_length = duration(minutes=60)

    source_temp_profile = {
        timestamp: 25 for timestamp in generate_market_slot_list(CURRENT_MARKET_SLOT)
    }
    consumption_profile = {
        timestamp: 5 for timestamp in generate_market_slot_list(CURRENT_MARKET_SLOT)
    }
    energy_params = HeatPumpEnergyParameters(
        maximum_power_rating_kW=30,
        tank_parameters=[
            WaterTankParameters(
                min_temp_C=10,
                max_temp_C=60,
                initial_temp_C=20,
                tank_volume_L=500,
            )
        ],
        source_temp_C_profile=source_temp_profile,
        consumption_kWh_profile=consumption_profile,
    )
    yield energy_params
    GlobalConfig.start_date = original_start_date
    GlobalConfig.sim_duration = original_sim_duration
    GlobalConfig.slot_length = original_slot_length


@pytest.fixture(name="energy_params_heat_profile")
def fixture_heatpump_energy_params_heat_profile() -> HeatPumpEnergyParameters:
    original_start_date = GlobalConfig.start_date
    original_sim_duration = GlobalConfig.sim_duration
    original_slot_length = GlobalConfig.slot_length
    GlobalConfig.start_date = CURRENT_MARKET_SLOT
    GlobalConfig.sim_duration = duration(days=1)
    GlobalConfig.slot_length = duration(minutes=60)

    source_temp_profile = {
        timestamp: 12 for timestamp in generate_market_slot_list(CURRENT_MARKET_SLOT)
    }
    heat_demand_profile = {
        timestamp: 9000000 for timestamp in generate_market_slot_list(CURRENT_MARKET_SLOT)
    }
    energy_params = HeatPumpEnergyParameters(
        maximum_power_rating_kW=30,
        tank_parameters=[
            WaterTankParameters(
                min_temp_C=10,
                max_temp_C=60,
                initial_temp_C=45,
                tank_volume_L=500,
            )
        ],
        source_temp_C_profile=source_temp_profile,
        heat_demand_Q_profile=heat_demand_profile,
        cop_model_type=COPModelType.HOVAL_ULTRASOURCE_B_COMFORT_C11,
    )
    yield energy_params
    GlobalConfig.start_date = original_start_date
    GlobalConfig.sim_duration = original_sim_duration
    GlobalConfig.slot_length = original_slot_length


class TestHeatPumpEnergyParameters:

    @staticmethod
    def test_event_activates_populates_profiles(energy_params):
        energy_params.event_activate()
        assert len(energy_params._consumption_kWh.profile) == 24
        assert len(energy_params._source_temp_C.profile) == 24

    @staticmethod
    @patch(
        "gsy_e.models.strategy.energy_parameters.heatpump.heat_pump."
        "HeatPumpEnergyParametersBase._populate_state",
        Mock(),
    )
    def test_event_market_cycle_populates_profiles(energy_params):
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        assert len(energy_params._consumption_kWh.profile) == 24
        assert len(energy_params._source_temp_C.profile) == 24

    @staticmethod
    def test_event_market_cycle_populates_state(energy_params):
        tank_state = energy_params._state._charger.tanks._tanks_states[0]
        heatpump_state = energy_params._state.heatpump
        assert CURRENT_MARKET_SLOT not in heatpump_state._min_energy_demand_kWh
        assert CURRENT_MARKET_SLOT not in heatpump_state._max_energy_demand_kWh
        energy_params.event_activate()
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        assert tank_state._storage_temp_C[CURRENT_MARKET_SLOT] == 20
        assert isclose(
            heatpump_state._min_energy_demand_kWh[CURRENT_MARKET_SLOT], 4.113, abs_tol=1e-3
        )
        assert isclose(
            heatpump_state._max_energy_demand_kWh[CURRENT_MARKET_SLOT], 8.546, abs_tol=1e-3
        )

    @staticmethod
    def test_event_traded_energy_decrements_posted_energy(energy_params):
        heatpump_state = energy_params._state.heatpump
        energy_params.event_activate()
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        traded_energy = 0.00001
        original_min_demand = heatpump_state._min_energy_demand_kWh[CURRENT_MARKET_SLOT]
        original_max_demand = heatpump_state._max_energy_demand_kWh[CURRENT_MARKET_SLOT]
        energy_params.event_traded_energy(CURRENT_MARKET_SLOT, traded_energy)
        assert (
            heatpump_state._min_energy_demand_kWh[CURRENT_MARKET_SLOT]
            == original_min_demand - traded_energy
        )
        assert (
            heatpump_state._max_energy_demand_kWh[CURRENT_MARKET_SLOT]
            == original_max_demand - traded_energy
        )

    @staticmethod
    def test_event_market_cycle_updates_temp_increase_if_energy_was_traded(energy_params):
        tank_state = energy_params._state._charger.tanks._tanks_states[0]
        energy_params.event_activate()
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        traded_energy = 6
        energy_params.event_traded_energy(CURRENT_MARKET_SLOT, traded_energy)
        next_market_slot = CURRENT_MARKET_SLOT + GlobalConfig.slot_length
        energy_params.event_market_cycle(next_market_slot)
        assert isclose(tank_state._storage_temp_C[next_market_slot], 31.280, rel_tol=0.0001)

    @staticmethod
    @pytest.mark.parametrize(
        "current_temp, expected_demand",
        [
            [10, 1.922],  # storage too cold, charging with _max_energy_consumption_kWh reached
            [20, 1.329],  # storage too cold, charging
            [30, 0.513],  # storage at min temp, only trade for heat demand
            [32, 0.317],  # storage does not need to be charged, can drop to min
            [35, 0.0],  # temp decrease due to demand is equal to drop to min, do not trade
            [37, 0.0],  # temp decrease due to demand is higher than the drop to min, do not trade
        ],
    )
    def test_get_min_energy_demand_kWh_returns_correct_value(
        energy_params, current_temp, expected_demand
    ):
        energy_params._max_energy_consumption_kWh = 2
        energy_params._state.heatpump.get_cop = Mock(return_value=5)
        energy_params._state.heatpump.get_heat_demand_kJ = Mock(return_value=10440)
        for tank_state in energy_params._state._charger.tanks._tanks_states:
            tank_state._params.min_temp_C = 30
            tank_state.get_storage_temp_C = Mock(return_value=current_temp)
        energy_params.event_activate()
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        assert isclose(
            energy_params.get_min_energy_demand_kWh(CURRENT_MARKET_SLOT),
            expected_demand,
            abs_tol=1e-3,
        )

    @staticmethod
    def test_get_max_energy_demand_kWh_returns_correct_value(energy_params):
        energy_params.event_activate()
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        energy_params.get_max_energy_demand_kWh(CURRENT_MARKET_SLOT)
        assert isclose(
            energy_params.get_max_energy_demand_kWh(CURRENT_MARKET_SLOT), 8.546, abs_tol=1e-3
        )

    @staticmethod
    def test_event_market_cycle_calculates_and_sets_cop(energy_params):
        assert energy_params._state.heatpump._cop[CURRENT_MARKET_SLOT] == 0
        energy_params.event_activate()
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        energy_params._bought_energy_kWh = 0.1
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT + duration(minutes=60))
        assert energy_params._state.heatpump._cop[CURRENT_MARKET_SLOT] == 6.5425

    @staticmethod
    def test_if_profiles_are_rotated_on_activate(energy_params):
        energy_params._consumption_kWh.read_or_rotate_profiles = Mock()
        energy_params._source_temp_C.read_or_rotate_profiles = Mock()
        energy_params.event_activate()
        energy_params._consumption_kWh.read_or_rotate_profiles.assert_called_once()
        energy_params._source_temp_C.read_or_rotate_profiles.assert_called_once()

    @staticmethod
    def test_if_profiles_are_rotated_on_market_cycle(energy_params):
        energy_params._consumption_kWh.read_or_rotate_profiles = Mock()
        energy_params._source_temp_C.read_or_rotate_profiles = Mock()
        energy_params._populate_state = Mock()
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        energy_params._consumption_kWh.read_or_rotate_profiles.assert_called_once()
        energy_params._source_temp_C.read_or_rotate_profiles.assert_called_once()
        energy_params._populate_state.assert_called_once()

    @staticmethod
    def test_cop_model_is_correctly_selected(energy_params_heat_profile):
        energy_params_heat_profile.event_activate()
        energy_params_heat_profile.event_market_cycle(CURRENT_MARKET_SLOT)
        energy_params_heat_profile._bought_energy_kWh = 1
        energy_params_heat_profile.event_market_cycle(CURRENT_MARKET_SLOT + duration(minutes=60))
        assert isclose(
            energy_params_heat_profile._state.heatpump.get_cop(CURRENT_MARKET_SLOT),
            3.979,
            abs_tol=0.001,
        )

    @staticmethod
    def test_event_market_cycle_triggers_delete_past_state_values(energy_params):
        # Given
        energy_params._state.delete_past_state_values = Mock()
        energy_params._populate_state = Mock()
        # When
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        # Then
        energy_params._state.delete_past_state_values.assert_called_once()
