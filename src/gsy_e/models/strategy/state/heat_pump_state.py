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
    convert_pendulum_to_str_in_dict)
from pendulum import DateTime, duration

from gsy_e import constants
from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.state.base_states import StateInterface, UnexpectedStateException


class HeatPumpState(StateInterface):
    # pylint: disable=too-many-instance-attributes
    """State for the heat pump strategy."""

    def __init__(
            self, initial_temp_C: float, min_temp_C: float,
            max_temp_C: float, slot_length: duration):
        # the defaultdict was only selected for the initial slot
        self._storage_temp_C: Dict[DateTime, float] = defaultdict(lambda: initial_temp_C)
        self._min_energy_demand_kWh: Dict[DateTime, float] = {}
        self._max_energy_demand_kWh: Dict[DateTime, float] = {}
        # buffers for increase and  decrease of storage
        self._temp_decrease_K: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._temp_increase_K: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._slot_length = slot_length
        self._min_temp_C = min_temp_C
        self._max_temp_C = max_temp_C

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

    def set_temp_decrease_K(self, time_slot: DateTime, temp_diff_K: float):
        """Set the temperature decrease for a given time slot."""
        if self._storage_temp_C[time_slot] - temp_diff_K < self._min_temp_C:
            self._temp_decrease_K[time_slot] = 0.
        else:
            self._temp_decrease_K[time_slot] = temp_diff_K

    def update_temp_increase_K(self, time_slot: DateTime, temp_diff_K: float):
        """Set the temperature increase for a given time slot."""
        self._temp_increase_K[time_slot] += temp_diff_K

    def get_min_energy_demand_kWh(self, time_slot: DateTime) -> float:
        """Return the minimal energy demanded for a given time slot."""
        return self._min_energy_demand_kWh.get(time_slot, 0)

    def get_max_energy_demand_kWh(self, time_slot: DateTime) -> float:
        """Return the maximal energy demanded for a given time slot."""
        return self._max_energy_demand_kWh.get(time_slot, 0)

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
            "min_energy_demand_kWh": convert_pendulum_to_str_in_dict(self._min_energy_demand_kWh),
            "max_energy_demand_kWh": convert_pendulum_to_str_in_dict(self._max_energy_demand_kWh),
        }

    def restore_state(self, state_dict: Dict):
        self._storage_temp_C = convert_pendulum_to_str_in_dict(state_dict["storage_temp_C"])
        self._temp_decrease_K = convert_pendulum_to_str_in_dict(state_dict["temp_decrease_K"])
        self._temp_increase_K = convert_pendulum_to_str_in_dict(state_dict["temp_increase_K"])
        self._min_energy_demand_kWh = convert_pendulum_to_str_in_dict(
            state_dict["min_energy_demand_kWh"])
        self._max_energy_demand_kWh = convert_pendulum_to_str_in_dict(
            state_dict["max_energy_demand_kWh"])

    def delete_past_state_values(self, current_time_slot: DateTime):
        if not current_time_slot or constants.RETAIN_PAST_MARKET_STRATEGIES_STATE:
            return
        self._delete_time_slots(self._min_energy_demand_kWh,
                                self._last_time_slot(current_time_slot))
        self._delete_time_slots(self._max_energy_demand_kWh,
                                self._last_time_slot(current_time_slot))
        self._delete_time_slots(self._storage_temp_C,
                                self._last_time_slot(current_time_slot))
        self._delete_time_slots(self._temp_increase_K,
                                self._last_time_slot(current_time_slot))
        self._delete_time_slots(self._temp_decrease_K,
                                self._last_time_slot(current_time_slot))

    def get_results_dict(self, current_time_slot: DateTime) -> Dict:
        return {
            "storage_temp_C": self.get_storage_temp_C(current_time_slot),
            "temp_decrease_K": self.get_temp_decrease_K(current_time_slot),
            "temp_increase_K": self.get_temp_increase_K(current_time_slot)
        }

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
