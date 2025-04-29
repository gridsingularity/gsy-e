from logging import getLogger
from statistics import mean
from typing import Union, List, Dict

from gsy_framework.constants_limits import FLOATING_POINT_TOLERANCE
from gsy_framework.utils import convert_kJ_to_kWh
from pendulum import DateTime

from gsy_e.models.strategy.state.heatpump_pcm_tank_state import PCMTankState
from gsy_e.models.strategy.state.heatpump_water_tank_state import WaterTankState, TankStateBase
from gsy_e.models.strategy.energy_parameters.heatpump.tank_parameters import (
    TankParameters,
    HeatpumpTankTypes,
)

log = getLogger(__name__)


def heatpump_state_factory(tank_parameter: TankParameters) -> TankStateBase:
    """Return correct Tank object from the type provided in the tank parameters."""
    if tank_parameter.type == HeatpumpTankTypes.WATER:
        return WaterTankState(tank_parameters=tank_parameter)
    if tank_parameter.type == HeatpumpTankTypes.PCM:
        return PCMTankState(tank_parameters=tank_parameter)
    assert False, f"Unsupported heat pump tank type {tank_parameter.type}"


class AllTanksState:
    """Manage the operation of heating and extracting temperature from multiple tanks."""

    def __init__(self, tank_parameters: List[TankParameters]):
        self.tanks_states = [heatpump_state_factory(tank) for tank in tank_parameters]

    def increase_tanks_temp_from_heat_energy(self, heat_energy_kJ: float, time_slot: DateTime):
        """Increase the temperature of the water tanks with the provided heat energy."""
        # Split heat energy equally across tanks
        heat_energy_per_tank_kJ = heat_energy_kJ / len(self.tanks_states)
        heat_energy_per_tank_kWh = convert_kJ_to_kWh(heat_energy_per_tank_kJ)
        for tank in self.tanks_states:
            tank.increase_tank_temp_from_heat_energy(heat_energy_per_tank_kWh, time_slot)

    def decrease_tanks_temp_from_heat_energy(self, heat_energy_kJ: float, time_slot: DateTime):
        """Decrease the temperature of the water tanks with the provided heat energy."""
        heat_energy_per_tank_kJ = heat_energy_kJ / len(self.tanks_states)
        heat_energy_per_tank_kWh = convert_kJ_to_kWh(heat_energy_per_tank_kJ)
        for tank in self.tanks_states:
            tank.decrease_tank_temp_from_heat_energy(heat_energy_per_tank_kWh, time_slot)

    def update_tanks_temperature(self, time_slot: DateTime):
        """
        Update the current temperature of all tanks, based on temp increase/decrease of the market
        slot.
        """
        for tank in self.tanks_states:
            # pylint: disable=protected-access
            tank.update_storage_temp(time_slot)

    def get_max_heat_energy_consumption_kJ(self, time_slot: DateTime):
        """Get max heat energy consumption from all water tanks."""
        max_energy_consumption_kJ = sum(
            tank.get_max_heat_energy_consumption_kJ(time_slot) for tank in self.tanks_states
        )
        assert max_energy_consumption_kJ > -FLOATING_POINT_TOLERANCE
        return max_energy_consumption_kJ

    def get_min_heat_energy_consumption_kJ(self, time_slot: DateTime):
        """Get min heat energy consumption from all water tanks."""
        min_energy_consumption_kJ = sum(
            tank.get_min_heat_energy_consumption_kJ(time_slot) for tank in self.tanks_states
        )
        assert min_energy_consumption_kJ > -FLOATING_POINT_TOLERANCE
        return min_energy_consumption_kJ

    def get_average_tank_temperature(self, time_slot: DateTime):
        """Get average tank temperature of all water tanks."""
        return mean(tank.current_tank_temperature(time_slot) for tank in self.tanks_states)

    def serialize(self) -> Union[Dict, List]:
        """Serializable dict with the parameters of all water tanks."""
        return [tank.serialize() for tank in self.tanks_states]

    def get_results_dict(self, current_time_slot: DateTime):
        """Results dict with the results from all water tanks."""
        if current_time_slot is None:
            return []
        return [tank.get_results_dict(current_time_slot) for tank in self.tanks_states]

    def get_state(self) -> Union[List, Dict]:
        """Get all tanks state."""
        return [tank.get_state() for tank in self.tanks_states]

    def restore_state(self, state_dict: dict):
        """Restore all tanks state."""
        for tank in self.tanks_states:
            tank.restore_state(state_dict)

    def delete_past_state_values(self, current_time_slot: DateTime):
        """Delete previous state from all tanks."""
        for tank in self.tanks_states:
            tank.delete_past_state_values(current_time_slot)

    def event_activate(self):
        """Perform steps when activate event is called"""
        for tank in self.tanks_states:
            tank.init()
