import logging
from dataclasses import dataclass
from statistics import mean
from typing import Dict, Union, List

from pendulum import DateTime

from gsy_framework.constants_limits import ConstSettings, GlobalConfig, FLOATING_POINT_TOLERANCE
from gsy_framework.utils import convert_kJ_to_kWh, convert_kWh_to_kJ

from gsy_e.models.strategy.energy_parameters.heatpump.constants import (
    WATER_DENSITY,
    SPECIFIC_HEAT_CONST_WATER,
)
from gsy_e.models.strategy.state import HeatPumpTankState

logger = logging.getLogger(__name__)


@dataclass
class TankParameters:
    """Nameplate parameters of a water tank."""

    min_temp_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C
    max_temp_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C
    initial_temp_C: float = ConstSettings.HeatPumpSettings.INIT_TEMP_C
    tank_volume_L: float = ConstSettings.HeatPumpSettings.TANK_VOL_L


class TankEnergyParameters:
    """Manage the operation of heating and extracting temperature from a single tank."""

    def __init__(self, tank_parameters: TankParameters, slot_length):
        self._parameters = tank_parameters
        self._state = HeatPumpTankState(
            initial_temp_C=tank_parameters.initial_temp_C,
            slot_length=slot_length,
            min_storage_temp_C=tank_parameters.min_temp_C,
            max_storage_temp_C=tank_parameters.max_temp_C,
        )

    @property
    def _Q_specific(self):
        return SPECIFIC_HEAT_CONST_WATER * self._parameters.tank_volume_L * WATER_DENSITY

    def serialize(self):
        """Serializable dict with the parameters of the water tank."""
        return {
            "max_temp_C": self._parameters.max_temp_C,
            "min_temp_C": self._parameters.min_temp_C,
            "tank_volume_l": self._parameters.tank_volume_L,
        }

    def get_results_dict(self, current_time_slot: DateTime):
        """Results dict with the results from the tank."""
        return self._state.get_results_dict(current_time_slot)

    def increase_tank_temp_from_heat_energy(self, heat_energy_kWh: float, time_slot: DateTime):
        """Increase the temperature of the water tank with the provided heat energy."""
        temp_increase_K = self._Q_kWh_to_temp_diff(heat_energy_kWh)
        self._state.update_temp_increase_K(time_slot, temp_increase_K)

    def decrease_tank_temp_from_heat_energy(self, heat_energy_kWh: float, time_slot: DateTime):
        """Decrease the temperature of the water tank with the provided heat energy."""
        temp_decrease_K = self._Q_kWh_to_temp_diff(heat_energy_kWh)
        self._state.set_temp_decrease_K(time_slot, temp_decrease_K)

    def increase_tank_temp_from_temp_delta(self, temp_diff: float, time_slot: DateTime):
        """Increase the tank temperature from temperature delta."""
        self._state.update_temp_increase_K(time_slot, temp_diff)

    def get_max_heat_energy_consumption_kWh(self, time_slot: DateTime):
        """Calculate max heat energy consumption that the tank can accomodate."""
        max_temp_diff = (
            self._parameters.max_temp_C
            - self._state.get_storage_temp_C(time_slot)
            + self._state.get_temp_decrease_K(time_slot)
        )

        return max_temp_diff * self._Q_specific

    def get_min_heat_energy_consumption_kWh(self, time_slot: DateTime):
        """
        Calculate min heat energy consumption that a heatpump has to consume in
        order to only let the storage drop its temperature to the minimum storage temperature.
        - if current_temp < min_storage_temp: charge till min_storage_temp is reached
        - if current_temp = min_storage_temp: only for the demanded energy
        - if current_temp > min_storage: only trade for the demand minus the heat
                                         that can be extracted from the storage
        """
        diff_to_min_temp_C = self._state.get_current_diff_to_min_temp_K(time_slot)
        temp_diff_due_to_consumption = self._state.get_temp_decrease_K(time_slot)
        min_temp_diff = (
            temp_diff_due_to_consumption - diff_to_min_temp_C
            if diff_to_min_temp_C <= temp_diff_due_to_consumption
            else 0
        )
        return min_temp_diff * self._Q_specific

    def current_tank_temperature(self, time_slot: DateTime) -> float:
        """Get current tank temperature for timeslot."""
        return self._state.get_storage_temp_C(time_slot)

    def get_unmatched_demand_kWh(self, time_slot: DateTime) -> float:
        """Get unmatched demand for timeslot."""
        temp_balance = self._state.get_temp_increase_K(
            time_slot
        ) - self._state.get_temp_decrease_K(time_slot)
        if temp_balance < FLOATING_POINT_TOLERANCE:
            return self._temp_diff_to_Q_kWh(abs(temp_balance))
        return 0.0

    def _temp_diff_to_Q_kWh(self, diff_temp_K: float) -> float:
        return diff_temp_K * self._Q_specific

    def _Q_kWh_to_temp_diff(self, energy_kWh: float) -> float:
        return energy_kWh / self._Q_specific


class AllTanksEnergyParameters:
    """Manage the operation of heating and extracting temperature from multiple tanks."""

    def __init__(self, tank_parameters: List[TankParameters]):
        self._tanks_energy_parameters = [
            TankEnergyParameters(tank, GlobalConfig.slot_length) for tank in tank_parameters
        ]

    def increase_tanks_temp_from_heat_energy(self, heat_energy_kJ: float, time_slot: DateTime):
        """Increase the temperature of the water tanks with the provided heat energy."""
        # Split heat energy equally across tanks
        heat_energy_per_tank_kJ = heat_energy_kJ / len(self._tanks_energy_parameters)
        heat_energy_per_tank_kWh = convert_kJ_to_kWh(heat_energy_per_tank_kJ)
        for tank in self._tanks_energy_parameters:
            tank.increase_tank_temp_from_heat_energy(heat_energy_per_tank_kWh, time_slot)

    def decrease_tanks_temp_from_heat_energy(self, heat_energy_kJ: float, time_slot: DateTime):
        """Decrease the temperature of the water tanks with the provided heat energy."""
        heat_energy_per_tank_kJ = heat_energy_kJ / len(self._tanks_energy_parameters)
        heat_energy_per_tank_kWh = convert_kJ_to_kWh(heat_energy_per_tank_kJ)
        for tank in self._tanks_energy_parameters:
            tank.decrease_tank_temp_from_heat_energy(heat_energy_per_tank_kWh, time_slot)

    def update_tanks_temperature(self, time_slot: DateTime):
        """
        Update the current temperature of all tanks, based on temp increase/decrease of the market
        slot.
        """
        for tank in self._tanks_energy_parameters:
            # pylint: disable=protected-access
            tank._state.update_storage_temp(time_slot)

    def get_max_heat_energy_consumption_kJ(self, time_slot: DateTime):
        """Get max heat energy consumption from all water tanks."""
        max_energy_consumption_kWh = sum(
            tank.get_max_heat_energy_consumption_kWh(time_slot)
            for tank in self._tanks_energy_parameters
        )
        assert max_energy_consumption_kWh > -FLOATING_POINT_TOLERANCE
        return convert_kWh_to_kJ(max_energy_consumption_kWh)

    def get_min_heat_energy_consumption_kJ(self, time_slot: DateTime):
        """Get min heat energy consumption from all water tanks."""
        min_energy_consumption_kWh = sum(
            tank.get_min_heat_energy_consumption_kWh(time_slot)
            for tank in self._tanks_energy_parameters
        )
        assert min_energy_consumption_kWh > -FLOATING_POINT_TOLERANCE
        return convert_kWh_to_kJ(min_energy_consumption_kWh)

    def get_average_tank_temperature(self, time_slot: DateTime):
        """Get average tank temperature of all water tanks."""
        return mean(
            tank.current_tank_temperature(time_slot) for tank in self._tanks_energy_parameters
        )

    def get_unmatched_demand_kWh(self, time_slot: DateTime):
        """Get unmatched demand of all water tanks."""
        return sum(
            tank.get_unmatched_demand_kWh(time_slot) for tank in self._tanks_energy_parameters
        )

    def serialize(self) -> Union[Dict, List]:
        """Serializable dict with the parameters of all water tanks."""
        # TODO: Convert the AVRO schemas to be able to serialize multiple tanks
        if len(self._tanks_energy_parameters) == 1:
            # Return a dict for the case of one tank, in order to not break other services that
            # support one single tank.
            return self._tanks_energy_parameters[0].serialize()
        return [tank.serialize() for tank in self._tanks_energy_parameters]

    def get_results_dict(self, current_time_slot: DateTime):
        """Results dict with the results from all water tanks."""
        if len(self._tanks_energy_parameters) == 1:
            # Return a dict for the case of one tank, in order to not break other services that
            # support one single tank.
            return self._tanks_energy_parameters[0].get_results_dict(current_time_slot)
        return [tank.get_results_dict(current_time_slot) for tank in self._tanks_energy_parameters]

    def get_state(self) -> Union[List, Dict]:
        """Get all tanks state."""
        # pylint: disable=protected-access
        if len(self._tanks_energy_parameters) == 1:
            # Return a dict for the case of one tank, in order to not break other services that
            # support one single tank.
            return self._tanks_energy_parameters[0]._state.get_state()
        return [tank._state.get_state() for tank in self._tanks_energy_parameters]

    def restore_state(self, state_dict: dict):
        """Restore all tanks state."""
        # pylint: disable=protected-access
        for tank in self._tanks_energy_parameters:
            tank._state.restore_state(state_dict)

    def delete_past_state_values(self, current_time_slot: DateTime):
        """Delete previous state from all tanks."""
        # pylint: disable=protected-access
        for tank in self._tanks_energy_parameters:
            tank._state.delete_past_state_values(current_time_slot)
