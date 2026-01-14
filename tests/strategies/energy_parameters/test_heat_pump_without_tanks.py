# pylint: disable=protected-access
from unittest.mock import Mock

import pytest
from gsy_framework.constants_limits import GlobalConfig, TIME_ZONE
from gsy_framework.utils import generate_market_slot_list
from pendulum import duration, today

from gsy_e.models.strategy.energy_parameters.heatpump.heat_pump import (
    HeatPumpEnergyParametersWithoutTanks,
)

CURRENT_MARKET_SLOT = today(tz=TIME_ZONE)
TARGET_TEMP_PROFILE = {
    timestamp: 25 for timestamp in generate_market_slot_list(CURRENT_MARKET_SLOT)
}
SOURCE_TEMP_PROFILE = {
    timestamp: 10 for timestamp in generate_market_slot_list(CURRENT_MARKET_SLOT)
}
CONSUMPTION_PROFILE = {
    timestamp: 1 for timestamp in generate_market_slot_list(CURRENT_MARKET_SLOT)
}
HEAT_PROFILE = {
    timestamp: 3600 * 5 for timestamp in generate_market_slot_list(CURRENT_MARKET_SLOT)
}


@pytest.fixture(name="energy_params")
def fixture_heatpump_energy_params() -> HeatPumpEnergyParametersWithoutTanks:
    original_slot_length = GlobalConfig.slot_length
    GlobalConfig.slot_length = duration(minutes=60)

    energy_params = HeatPumpEnergyParametersWithoutTanks(
        target_temp_C_profile=TARGET_TEMP_PROFILE,
        source_temp_C_profile=SOURCE_TEMP_PROFILE,
        consumption_kWh_profile=CONSUMPTION_PROFILE,
    )
    yield energy_params
    GlobalConfig.slot_length = original_slot_length


@pytest.fixture(name="energy_params_heat_profile")
def fixture_heatpump_energy_params_heat_profile() -> HeatPumpEnergyParametersWithoutTanks:
    original_slot_length = GlobalConfig.slot_length
    GlobalConfig.slot_length = duration(minutes=60)

    energy_params = HeatPumpEnergyParametersWithoutTanks(
        target_temp_C_profile=TARGET_TEMP_PROFILE,
        source_temp_C_profile=SOURCE_TEMP_PROFILE,
        heat_demand_Q_profile=HEAT_PROFILE,
    )
    yield energy_params
    GlobalConfig.slot_length = original_slot_length


class TestHeatPumpParametersWithoutTanks:

    def test_event_activate_rotates_profiles_for_the_first_times(self, energy_params):
        # Given
        assert CURRENT_MARKET_SLOT not in energy_params._consumption_kWh.profile
        assert CURRENT_MARKET_SLOT not in energy_params._source_temp_C.profile
        assert CURRENT_MARKET_SLOT not in energy_params._target_temp_C.profile
        # When
        energy_params.event_activate()
        # Then
        assert energy_params._consumption_kWh.get_value(CURRENT_MARKET_SLOT) == 1
        assert energy_params._source_temp_C.get_value(CURRENT_MARKET_SLOT) == 10
        assert energy_params._target_temp_C.get_value(CURRENT_MARKET_SLOT) == 25

    def test_event_market_cycle_rotates_profiles(self, energy_params):
        # Given
        assert CURRENT_MARKET_SLOT not in energy_params._consumption_kWh.profile
        assert CURRENT_MARKET_SLOT not in energy_params._source_temp_C.profile
        assert CURRENT_MARKET_SLOT not in energy_params._target_temp_C.profile
        # When
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        # Then
        assert energy_params._consumption_kWh.get_value(CURRENT_MARKET_SLOT) == 1
        assert energy_params._source_temp_C.get_value(CURRENT_MARKET_SLOT) == 10
        assert energy_params._target_temp_C.get_value(CURRENT_MARKET_SLOT) == 25

    def test_event_market_cycle_populates_state_correctly(self, energy_params):
        # Given
        current_market_slot = CURRENT_MARKET_SLOT + duration(minutes=60)
        last_market_slot = CURRENT_MARKET_SLOT
        energy_params.event_activate()
        energy_params._calc_cop = Mock(return_value=5)
        energy_params._calc_Q_kJ_from_energy_kWh = Mock(return_value=5000)
        energy_params._bought_energy_kWh = 1
        # When
        # Event market cycle has to be called twice in order to have a last_market_slot
        energy_params.event_market_cycle(last_market_slot)
        energy_params.event_market_cycle(current_market_slot)
        # Then
        energy_params._state._cop[last_market_slot] = 5
        energy_params._state._cop[current_market_slot] = 5
        assert energy_params._bought_energy_kWh == 0
        assert energy_params._consumption_kWh.get_value(current_market_slot) == 1
        assert energy_params._state._heat_demand_kJ[current_market_slot] == 5000
        assert energy_params._state._energy_demand_kWh[current_market_slot] == 1

    def test_event_market_cycle_populates_state_correctly_heat_profile(
        self, energy_params_heat_profile
    ):
        # Given
        current_market_slot = CURRENT_MARKET_SLOT + duration(minutes=60)
        last_market_slot = CURRENT_MARKET_SLOT
        energy_params_heat_profile.event_activate()
        energy_params_heat_profile._calc_cop = Mock(return_value=5)
        energy_params_heat_profile._calc_Q_kJ_from_energy_kWh = Mock(return_value=5000)
        energy_params_heat_profile._bought_energy_kWh = 1
        # When
        # Event market cycle has to be called twice in order to have a last_market_slot
        energy_params_heat_profile.event_market_cycle(last_market_slot)
        energy_params_heat_profile.event_market_cycle(current_market_slot)
        # Then
        energy_params_heat_profile._state._cop[last_market_slot] = 5
        energy_params_heat_profile._state._cop[current_market_slot] = 5
        assert energy_params_heat_profile._bought_energy_kWh == 0
        assert current_market_slot not in energy_params_heat_profile._consumption_kWh.profile
        assert energy_params_heat_profile._state._heat_demand_kJ[current_market_slot] == 18
        assert energy_params_heat_profile._state._energy_demand_kWh[current_market_slot] == 0.001

    def test_event_traded_energy_increases_energies(self, energy_params):
        # Given
        energy_params.event_activate()
        # When
        energy_params.event_traded_energy(CURRENT_MARKET_SLOT, 2)
        # Then
        assert energy_params._bought_energy_kWh == 2

    def test_serialize_returns_correct_input_arguments(self, energy_params):
        # When
        serialized = energy_params.serialize()
        # Then
        assert serialized["consumption_kWh"] == CONSUMPTION_PROFILE
        assert serialized["source_temp_C"] == SOURCE_TEMP_PROFILE
        assert serialized["target_temp_C"] == TARGET_TEMP_PROFILE
        assert serialized["consumption_profile_uuid"] is None
        assert serialized["source_temp_C_profile_uuid"] is None
        assert serialized["target_temp_C_profile_uuid"] is None
        assert serialized["source_type"] == 0
        assert serialized["heat_demand_Q_profile"] is None
        assert serialized["cop_model_type"] == 0

    def test_get_energy_demand_kWh_returns_correct_value(self, energy_params):
        # Given
        energy_params.event_activate()
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        # When / Then
        assert energy_params.get_energy_demand_kWh(CURRENT_MARKET_SLOT) == 1

    def test_get_energy_demand_kWh_returns_correct_value_heat_profile(
        self, energy_params_heat_profile
    ):
        # Given
        energy_params_heat_profile.state.get_cop = Mock(return_value=5)
        energy_params_heat_profile.event_activate()
        energy_params_heat_profile.event_market_cycle(CURRENT_MARKET_SLOT)
        # When / Then
        assert energy_params_heat_profile.get_energy_demand_kWh(CURRENT_MARKET_SLOT) == 0.001
