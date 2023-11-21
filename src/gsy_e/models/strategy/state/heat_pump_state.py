"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from collections import defaultdict
from typing import Dict

from gsy_framework.utils import (
    convert_pendulum_to_str_in_dict, convert_str_to_pendulum_in_dict)
from pendulum import DateTime, duration

from gsy_e import constants
from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.state.base_states import StateInterface, UnexpectedStateException


class HeatPumpState(StateInterface):
    # pylint: disable=too-many-instance-attributes
    """State for the heat pump strategy."""

    def __init__(
            self, initial_temp_C: float, slot_length: duration):
        # the defaultdict was only selected for the initial slot
        self._storage_temp_C: Dict[DateTime, float] = defaultdict(lambda: initial_temp_C)
        self._min_energy_demand_kWh: Dict[DateTime, float] = {}
        self._max_energy_demand_kWh: Dict[DateTime, float] = {}
        # buffers for increase and  decrease of storage
        self._temp_decrease_K: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._temp_increase_K: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._energy_consumption_kWh: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._total_traded_energy_kWh: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._slot_length = slot_length

    def get_storage_temp_C(self, time_slot: DateTime) -> float:
        """Return temperature of storage for a time slot in degree celsius."""
        return self._storage_temp_C[time_slot]

    def update_storage_temp(self, current_time_slot: DateTime):
        """Update storage temperature of the given slot with the accumulated changes. """
        new_temp = (self.get_storage_temp_C(self._last_time_slot(current_time_slot))
                    - self.get_temp_decrease_K(self._last_time_slot(current_time_slot))
                    + self.get_temp_increase_K(self._last_time_slot(current_time_slot)))
        if new_temp < -FLOATING_POINT_TOLERANCE:
            raise UnexpectedStateException("Storage of heat pump should not drop below zero.")
        self._storage_temp_C[current_time_slot] = new_temp

    def set_min_energy_demand_kWh(self, time_slot: DateTime, energy_kWh: float):
        """Set the minimal energy demanded for a given time slot."""
        self._min_energy_demand_kWh[time_slot] = energy_kWh

    def set_max_energy_demand_kWh(self, time_slot: DateTime, energy_kWh: float):
        """Set the maximal energy demanded for a given time slot."""
        self._max_energy_demand_kWh[time_slot] = energy_kWh

    def increase_total_traded_energy_kWh(self, time_slot: DateTime, energy_kWh: float):
        """Add to the total traded energy of the heatpump for a given time slot."""
        self._total_traded_energy_kWh[time_slot] += energy_kWh

    def set_temp_decrease_K(self, time_slot: DateTime, temp_diff_K: float):
        """Set the temperature decrease for a given time slot."""
        temp_decrease = temp_diff_K
        # Do not allow temperature to go below zero
        if self._storage_temp_C[time_slot] - temp_diff_K < -FLOATING_POINT_TOLERANCE:
            temp_decrease = self._storage_temp_C[time_slot]
        self._temp_decrease_K[time_slot] = temp_decrease

    def set_energy_consumption_kWh(self, time_slot: DateTime, energy_kWh: float):
        """Set the energy consumption of the heatpump for a given time slot."""
        self._energy_consumption_kWh[time_slot] = energy_kWh

    def update_energy_consumption_kWh(self, time_slot: DateTime, energy_kWh: float):
        """Update the energy consumption of the heatpump for a given time slot."""
        self._energy_consumption_kWh[time_slot] += energy_kWh

    def update_temp_increase_K(self, time_slot: DateTime, temp_diff_K: float):
        """Set the temperature increase for a given time slot."""
        self._temp_increase_K[time_slot] += temp_diff_K

    def get_min_energy_demand_kWh(self, time_slot: DateTime) -> float:
        """Return the minimal energy demanded for a given time slot."""
        return self._min_energy_demand_kWh.get(time_slot, 0)

    def get_max_energy_demand_kWh(self, time_slot: DateTime) -> float:
        """Return the maximal energy demanded for a given time slot."""
        return self._max_energy_demand_kWh.get(time_slot, 0)

    def get_energy_consumption_kWh(self, time_slot: DateTime) -> float:
        """Return the temperature increase for a given time slot."""
        return self._energy_consumption_kWh.get(time_slot, 0)

    def get_temp_decrease_K(self, time_slot: DateTime) -> float:
        """Return the temperature decrease for a given time slot."""
        return self._temp_decrease_K.get(time_slot, 0)

    def get_temp_increase_K(self, time_slot: DateTime) -> float:
        """Return the temperature increase for a given time slot."""
        return self._temp_increase_K.get(time_slot, 0)

    def get_state(self) -> Dict:
        return {
            "storage_temp_C": convert_pendulum_to_str_in_dict(self._storage_temp_C),
            "temp_decrease_K": convert_pendulum_to_str_in_dict(self._temp_decrease_K),
            "temp_increase_K": convert_pendulum_to_str_in_dict(self._temp_increase_K),
            "energy_consumption_kWh": convert_pendulum_to_str_in_dict(
                self._energy_consumption_kWh),
            "min_energy_demand_kWh": convert_pendulum_to_str_in_dict(self._min_energy_demand_kWh),
            "max_energy_demand_kWh": convert_pendulum_to_str_in_dict(self._max_energy_demand_kWh),
            "total_traded_energy_kWh": convert_pendulum_to_str_in_dict(
                self._total_traded_energy_kWh),
        }

    def restore_state(self, state_dict: Dict):
        self._storage_temp_C = convert_str_to_pendulum_in_dict(state_dict["storage_temp_C"])
        self._temp_decrease_K = convert_str_to_pendulum_in_dict(state_dict["temp_decrease_K"])
        self._temp_increase_K = convert_str_to_pendulum_in_dict(state_dict["temp_increase_K"])
        self._energy_consumption_kWh = convert_str_to_pendulum_in_dict(
            state_dict["energy_consumption_kWh"])
        self._min_energy_demand_kWh = convert_str_to_pendulum_in_dict(
            state_dict["min_energy_demand_kWh"])
        self._max_energy_demand_kWh = convert_str_to_pendulum_in_dict(
            state_dict["max_energy_demand_kWh"])
        self._total_traded_energy_kWh = convert_str_to_pendulum_in_dict(
            state_dict["total_traded_energy_kWh"])

    def delete_past_state_values(self, current_time_slot: DateTime):
        if not current_time_slot or constants.RETAIN_PAST_MARKET_STRATEGIES_STATE:
            return
        self._delete_time_slots(self._min_energy_demand_kWh,
                                self._last_time_slot(current_time_slot))
        self._delete_time_slots(self._max_energy_demand_kWh,
                                self._last_time_slot(current_time_slot))
        self._delete_time_slots(self._energy_consumption_kWh,
                                self._last_time_slot(current_time_slot))
        self._delete_time_slots(self._storage_temp_C,
                                self._last_time_slot(current_time_slot))
        self._delete_time_slots(self._temp_increase_K,
                                self._last_time_slot(current_time_slot))
        self._delete_time_slots(self._temp_decrease_K,
                                self._last_time_slot(current_time_slot))

    def get_results_dict(self, current_time_slot: DateTime) -> Dict:
        retval = {
            "storage_temp_C": self.get_storage_temp_C(current_time_slot),
            "temp_decrease_K": self.get_temp_decrease_K(current_time_slot),
            "temp_increase_K": self.get_temp_increase_K(current_time_slot),
            "energy_consumption_kWh": self.get_energy_consumption_kWh(current_time_slot),
            "max_energy_demand_kWh": self.get_max_energy_demand_kWh(current_time_slot),
            "min_energy_demand_kWh": self.get_min_energy_demand_kWh(current_time_slot),
            "total_traded_energy_kWh": self._total_traded_energy_kWh[current_time_slot],
        }
        return retval

    def _last_time_slot(self, current_market_slot: DateTime) -> DateTime:
        return current_market_slot - self._slot_length

    @staticmethod
    def _delete_time_slots(profile: Dict, current_time_stamp: DateTime):
        stamps_to_delete = []
        for time_slot in profile:
            if time_slot < current_time_stamp:
                stamps_to_delete.append(time_slot)
        for stamp in stamps_to_delete:
            profile.pop(stamp, None)

    def __str__(self):
        return self.__class__.__name__
