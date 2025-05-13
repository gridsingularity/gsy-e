from logging import getLogger
from statistics import mean
from typing import Union, List, Dict

from gsy_framework.constants_limits import FLOATING_POINT_TOLERANCE, GlobalConfig
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
        scaling_factors = self._get_scaling_factors_for_charging_energy(
            self._last_time_slot(time_slot)
        )
        for num, tank in enumerate(self.tanks_states):
            heat_energy_per_tank_kWh = convert_kJ_to_kWh(heat_energy_kJ * scaling_factors[num])
            tank.increase_tank_temp_from_heat_energy(heat_energy_per_tank_kWh, time_slot)

    def decrease_tanks_temp_from_heat_energy(self, heat_energy_kJ: float, time_slot: DateTime):
        """Decrease the temperature of the water tanks with the provided heat energy."""
        scaling_factors = self._get_scaling_factors_for_discharging(
            self._last_time_slot(time_slot)
        )
        for num, tank in enumerate(self.tanks_states):
            heat_energy_per_tank_kWh = convert_kJ_to_kWh(heat_energy_kJ * scaling_factors[num])
            tank.decrease_tank_temp_from_heat_energy(heat_energy_per_tank_kWh, time_slot)

    def no_charge(self, time_slot: DateTime):
        """Trigger no_charge method for all tanks"""
        for tank in self.tanks_states:
            tank.no_charge(time_slot)

    def update_tanks_temperature(self, time_slot: DateTime):
        """
        Update the current temperature of all tanks, based on temp increase/decrease of the market
        slot.
        """
        for tank in self.tanks_states:
            # pylint: disable=protected-access
            tank.update_storage_temp(time_slot)

    def get_max_heat_energy_consumption_kJ(self, time_slot: DateTime, heat_demand_kJ: float):
        """Get max heat energy consumption from all water tanks."""
        max_heat_energies = []
        scaling_factors = self._get_scaling_factors_for_discharging(time_slot)
        for num, tank in enumerate(self.tanks_states):
            max_heat_energy_per_tank = heat_demand_kJ * scaling_factors[num]
            max_heat_energies.append(
                tank.get_max_heat_energy_consumption_kJ(time_slot, max_heat_energy_per_tank)
            )

        max_energy_consumption_kJ = sum(max_heat_energies)
        assert max_energy_consumption_kJ > -FLOATING_POINT_TOLERANCE
        return max_energy_consumption_kJ

    def get_min_heat_energy_consumption_kJ(self, time_slot: DateTime, heat_demand_kJ: float):
        """Get min heat energy consumption from all water tanks."""
        min_heat_energies = []
        scaling_factors = self._get_scaling_factors_for_discharging(time_slot)
        for num, tank in enumerate(self.tanks_states):
            min_heat_energy_per_tank = heat_demand_kJ * scaling_factors[num]
            min_heat_energies.append(
                tank.get_min_heat_energy_consumption_kJ(time_slot, min_heat_energy_per_tank)
            )

        min_energy_consumption_kJ = sum(min_heat_energies)
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

    def _get_scaling_factors_for_charging_energy(self, time_slot):
        _current_dod_tanks = [tank.get_dod_energy_kJ(time_slot) for tank in self.tanks_states]
        total_energy = sum(_current_dod_tanks)
        if total_energy == 0:
            log.warning("No available space for charging in any tank. Skipping charging.")
            return [0] * len(self.tanks_states)
        return [energy / total_energy for energy in _current_dod_tanks]

    def _get_scaling_factors_for_discharging(self, time_slot):
        available_energies = [
            tank.get_available_energy_kJ(time_slot) for tank in self.tanks_states
        ]
        total_available_energy = sum(available_energies)
        if total_available_energy == 0:
            log.warning(
                "No available capacity for discharging in any tanks. Skipping discharging."
            )
            return [0] * len(self.tanks_states)
        return [energy / total_available_energy for energy in available_energies]

    def _last_time_slot(self, time_slot: DateTime):
        return time_slot - GlobalConfig.slot_length
