# pylint: disable=protected-access
from unittest.mock import Mock

import pytest
from gsy_framework.constants_limits import GlobalConfig, TIME_ZONE
from gsy_framework.utils import generate_market_slot_list
from pendulum import duration, today

from gsy_e.models.strategy.energy_parameters.heatpump.virtual_heat_pump import (
    VirtualHeatpumpEnergyParameters,
)
from gsy_e.models.strategy.energy_parameters.heatpump.tank import TankParameters

CURRENT_MARKET_SLOT = today(tz=TIME_ZONE)


@pytest.fixture(name="virtual_energy_params")
def fixture_heatpump_virtual_energy_params() -> VirtualHeatpumpEnergyParameters:
    original_start_date = GlobalConfig.start_date
    original_sim_duration = GlobalConfig.sim_duration
    original_slot_length = GlobalConfig.slot_length
    GlobalConfig.start_date = CURRENT_MARKET_SLOT
    GlobalConfig.sim_duration = duration(days=1)
    GlobalConfig.slot_length = duration(minutes=60)

    profile = {timestamp: 25 for timestamp in generate_market_slot_list(CURRENT_MARKET_SLOT)}
    virtual_energy_params = VirtualHeatpumpEnergyParameters(
        maximum_power_rating_kW=30,
        tank_parameters=[
            TankParameters(
                min_temp_C=10,
                max_temp_C=60,
                initial_temp_C=20,
                tank_volume_L=500,
            )
        ],
        water_supply_temp_C_profile=profile,
        water_return_temp_C_profile=profile,
        dh_water_flow_m3_profile=profile,
    )
    yield virtual_energy_params
    GlobalConfig.start_date = original_start_date
    GlobalConfig.sim_duration = original_sim_duration
    GlobalConfig.slot_length = original_slot_length


class TestVirtualHeatPumpParameters:

    @staticmethod
    def test_if_profiles_are_rotated_on_activate(virtual_energy_params):
        virtual_energy_params._water_supply_temp_C.read_or_rotate_profiles = Mock()
        virtual_energy_params._water_return_temp_C.read_or_rotate_profiles = Mock()
        virtual_energy_params._dh_water_flow_m3.read_or_rotate_profiles = Mock()
        virtual_energy_params.event_activate()
        virtual_energy_params._water_supply_temp_C.read_or_rotate_profiles.assert_called_once()
        virtual_energy_params._water_return_temp_C.read_or_rotate_profiles.assert_called_once()
        virtual_energy_params._dh_water_flow_m3.read_or_rotate_profiles.assert_called_once()

    @staticmethod
    def test_if_profiles_are_rotated_on_market_cycle(virtual_energy_params):
        virtual_energy_params._water_supply_temp_C.read_or_rotate_profiles = Mock()
        virtual_energy_params._water_supply_temp_C.get_value = Mock(return_value=1)
        virtual_energy_params._water_return_temp_C.read_or_rotate_profiles = Mock()
        virtual_energy_params._water_return_temp_C.get_value = Mock(return_value=1)
        virtual_energy_params._dh_water_flow_m3.read_or_rotate_profiles = Mock()
        virtual_energy_params._populate_state = Mock()
        virtual_energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        virtual_energy_params._water_supply_temp_C.read_or_rotate_profiles.assert_called_once()
        virtual_energy_params._water_return_temp_C.read_or_rotate_profiles.assert_called_once()
        virtual_energy_params._dh_water_flow_m3.read_or_rotate_profiles.assert_called_once()
        virtual_energy_params._populate_state.assert_called_once()
