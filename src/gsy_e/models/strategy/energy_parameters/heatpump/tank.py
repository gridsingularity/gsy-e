import logging
from statistics import mean
from typing import Dict, Union, List

from gsy_framework.constants_limits import GlobalConfig, FLOATING_POINT_TOLERANCE
from gsy_framework.utils import convert_kJ_to_kWh, convert_kWh_to_kJ
from pendulum import DateTime

from gsy_e.models.strategy.state.heat_pump_state import TankParameters, HeatPumpTankState

logger = logging.getLogger(__name__)


class AllTanksState:
    """Manage the operation of heating and extracting temperature from multiple tanks."""

    def __init__(self, tank_parameters: List[TankParameters]):
        self._tanks_states = [
            HeatPumpTankState(tank, GlobalConfig.slot_length) for tank in tank_parameters
        ]

    def increase_tanks_temp_from_heat_energy(self, heat_energy_kJ: float, time_slot: DateTime):
        """Increase the temperature of the water tanks with the provided heat energy."""
        # Split heat energy equally across tanks
        heat_energy_per_tank_kJ = heat_energy_kJ / len(self._tanks_states)
        heat_energy_per_tank_kWh = convert_kJ_to_kWh(heat_energy_per_tank_kJ)
        for tank in self._tanks_states:
            tank.increase_tank_temp_from_heat_energy(heat_energy_per_tank_kWh, time_slot)

    def decrease_tanks_temp_from_heat_energy(self, heat_energy_kJ: float, time_slot: DateTime):
        """Decrease the temperature of the water tanks with the provided heat energy."""
        heat_energy_per_tank_kJ = heat_energy_kJ / len(self._tanks_states)
        heat_energy_per_tank_kWh = convert_kJ_to_kWh(heat_energy_per_tank_kJ)
        for tank in self._tanks_states:
            tank.decrease_tank_temp_from_heat_energy(heat_energy_per_tank_kWh, time_slot)

    def update_tanks_temperature(self, time_slot: DateTime):
        """
        Update the current temperature of all tanks, based on temp increase/decrease of the market
        slot.
        """
        for tank in self._tanks_states:
            # pylint: disable=protected-access
            tank.update_storage_temp(time_slot)

    def get_max_heat_energy_consumption_kJ(self, time_slot: DateTime):
        """Get max heat energy consumption from all water tanks."""
        max_energy_consumption_kWh = sum(
            tank.get_max_heat_energy_consumption_kWh(time_slot) for tank in self._tanks_states
        )
        assert max_energy_consumption_kWh > -FLOATING_POINT_TOLERANCE
        return convert_kWh_to_kJ(max_energy_consumption_kWh)

    def get_min_heat_energy_consumption_kJ(self, time_slot: DateTime):
        """Get min heat energy consumption from all water tanks."""
        min_energy_consumption_kWh = sum(
            tank.get_min_heat_energy_consumption_kWh(time_slot) for tank in self._tanks_states
        )
        assert min_energy_consumption_kWh > -FLOATING_POINT_TOLERANCE
        return convert_kWh_to_kJ(min_energy_consumption_kWh)

    def get_average_tank_temperature(self, time_slot: DateTime):
        """Get average tank temperature of all water tanks."""
        return mean(tank.current_tank_temperature(time_slot) for tank in self._tanks_states)

    def get_unmatched_demand_kWh(self, time_slot: DateTime):
        """Get unmatched demand of all water tanks."""
        return sum(tank.get_unmatched_demand_kWh(time_slot) for tank in self._tanks_states)

    def serialize(self) -> Union[Dict, List]:
        """Serializable dict with the parameters of all water tanks."""
        # TODO: Convert the AVRO schemas to be able to serialize multiple tanks
        if len(self._tanks_states) == 1:
            # Return a dict for the case of one tank, in order to not break other services that
            # support one single tank.
            return self._tanks_states[0].serialize()
        return [tank.serialize() for tank in self._tanks_states]

    def get_results_dict(self, current_time_slot: DateTime):
        """Results dict with the results from all water tanks."""
        if len(self._tanks_states) == 1:
            # Return a dict for the case of one tank, in order to not break other services that
            # support one single tank.
            return self._tanks_states[0].get_results_dict(current_time_slot)
        return [tank.get_results_dict(current_time_slot) for tank in self._tanks_states]

    def get_state(self) -> Union[List, Dict]:
        """Get all tanks state."""
        # pylint: disable=protected-access
        if len(self._tanks_states) == 1:
            # Return a dict for the case of one tank, in order to not break other services that
            # support one single tank.
            return self._tanks_states[0].get_state()
        return [tank.get_state() for tank in self._tanks_states]

    def restore_state(self, state_dict: dict):
        """Restore all tanks state."""
        # pylint: disable=protected-access
        for tank in self._tanks_states:
            tank.restore_state(state_dict)

    def delete_past_state_values(self, current_time_slot: DateTime):
        """Delete previous state from all tanks."""
        # pylint: disable=protected-access
        for tank in self._tanks_states:
            tank.delete_past_state_values(current_time_slot)
