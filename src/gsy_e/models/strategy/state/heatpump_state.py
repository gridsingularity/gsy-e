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
from logging import getLogger
from typing import Dict

from gsy_framework.utils import (
    convert_pendulum_to_str_in_dict,
    convert_str_to_pendulum_in_dict,
)
from gsy_framework.constants_limits import GlobalConfig
from pendulum import DateTime

from gsy_e import constants
from gsy_e.models.strategy.state.base_states import StateInterface

log = getLogger(__name__)


def delete_time_slots_in_state(profile: Dict, current_time_stamp: DateTime):
    """Remove time slots older than the current_time_stamp from the profile."""
    stamps_to_delete = []
    for time_slot in profile:
        if time_slot < current_time_stamp:
            stamps_to_delete.append(time_slot)
    for stamp in stamps_to_delete:
        profile.pop(stamp, None)


class HeatPumpStateBase(StateInterface):
    """Base clase for Heat Pump strategy states"""

    def __init__(self):
        self._energy_demand_kWh: Dict[DateTime, float] = {}
        self._energy_consumption_kWh: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._cop: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._heat_demand_kJ: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._total_traded_energy_kWh: float = 0

    def get_energy_demand_kWh(self, time_slot: DateTime) -> float:
        """Return the energy demanded for a given time slot."""
        return self._energy_demand_kWh.get(time_slot, 0)

    def set_energy_demand_kWh(self, time_slot: DateTime, energy_kWh: float):
        """Set the minimal energy demanded for a given time slot."""
        self._energy_demand_kWh[time_slot] = energy_kWh

    def set_heat_demand_kJ(self, time_slot: DateTime, heat_demand_kJ: float):
        """Set heat demand for the given time slot."""
        self._heat_demand_kJ[time_slot] = heat_demand_kJ

    def get_heat_demand_kJ(self, time_slot: DateTime) -> float:
        """Return the heat demand in J for a given time slot."""
        return self._heat_demand_kJ.get(time_slot, 0)

    def increase_total_traded_energy_kWh(self, energy_kWh: float):
        """Add to the total traded energy of the heatpump for a given time slot."""
        self._total_traded_energy_kWh += energy_kWh

    def get_cop(self, time_slot: DateTime) -> float:
        """Return the cop for a given time slot."""
        return self._cop.get(time_slot, 0)

    def set_cop(self, time_slot: DateTime, cop: float):
        """Set cop for the given time slot."""
        self._cop[time_slot] = cop

    def _last_time_slot(self, current_market_slot: DateTime) -> DateTime:
        return current_market_slot - GlobalConfig.slot_length

    @staticmethod
    def _delete_time_slots(profile: Dict, current_time_stamp: DateTime):
        delete_time_slots_in_state(profile, current_time_stamp)

    def delete_past_state_values(self, current_time_slot: DateTime):
        if not current_time_slot or constants.RETAIN_PAST_MARKET_STRATEGIES_STATE:
            return
        last_time_slot = self._last_time_slot(current_time_slot)
        self._delete_time_slots(self._cop, last_time_slot)
        self._delete_time_slots(self._heat_demand_kJ, last_time_slot)

    def get_state(self) -> Dict:
        return {
            "cop": convert_pendulum_to_str_in_dict(self._cop),
            "heat_demand_kJ": convert_pendulum_to_str_in_dict(self._heat_demand_kJ),
        }

    def restore_state(self, state_dict: Dict):
        self._cop = convert_str_to_pendulum_in_dict(state_dict["cop"])
        self._heat_demand_kJ = convert_str_to_pendulum_in_dict(state_dict["heat_demand_kJ"])

    def get_results_dict(self, current_time_slot: DateTime) -> Dict:
        retval = {
            "cop": self.get_cop(current_time_slot),
            "heat_demand_kJ": self.get_heat_demand_kJ(current_time_slot),
        }
        return retval


class HeatPumpState(HeatPumpStateBase):
    """State for the heat pump strategy with tanks"""

    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        super().__init__()
        self._min_energy_demand_kWh: Dict[DateTime, float] = {}
        self._max_energy_demand_kWh: Dict[DateTime, float] = {}
        self._condenser_temp_C: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._net_heat_consumed_kJ: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._condenser_temp_C: Dict[DateTime, float] = defaultdict(lambda: 0)

    def set_net_heat_consumed_kJ(self, time_slot: DateTime, heat_energy_kJ: float):
        """Set net heat consumed."""
        self._net_heat_consumed_kJ[time_slot] = heat_energy_kJ

    def get_net_heat_consumed_kJ(self, time_slot: DateTime) -> float:
        """Return net heat consumed for provided market slot."""
        return self._net_heat_consumed_kJ.get(time_slot, 0)

    def set_min_energy_demand_kWh(self, time_slot: DateTime, energy_kWh: float):
        """Set the minimal energy demanded for a given time slot."""
        self._min_energy_demand_kWh[time_slot] = energy_kWh

    def set_max_energy_demand_kWh(self, time_slot: DateTime, energy_kWh: float):
        """Set the maximal energy demanded for a given time slot."""
        self._max_energy_demand_kWh[time_slot] = energy_kWh

    def set_energy_consumption_kWh(self, time_slot: DateTime, energy_kWh: float):
        """Set the energy consumption of the heatpump for a given time slot."""
        self._energy_consumption_kWh[time_slot] = energy_kWh

    def set_condenser_temp(self, time_slot: DateTime, condenser_temp_C: float):
        """Set condenser temperature for the given time slot."""
        self._condenser_temp_C[time_slot] = condenser_temp_C

    def update_energy_consumption_kWh(self, time_slot: DateTime, energy_kWh: float):
        """Update the energy consumption of the heatpump for a given time slot."""
        self._energy_consumption_kWh[time_slot] += energy_kWh

    def get_min_energy_demand_kWh(self, time_slot: DateTime) -> float:
        """Return the minimal energy demanded for a given time slot."""
        return self._min_energy_demand_kWh.get(time_slot, 0)

    def get_max_energy_demand_kWh(self, time_slot: DateTime) -> float:
        """Return the maximal energy demanded for a given time slot."""
        return self._max_energy_demand_kWh.get(time_slot, 0)

    def get_energy_consumption_kWh(self, time_slot: DateTime) -> float:
        """Return the temperature increase for a given time slot."""
        return self._energy_consumption_kWh.get(time_slot, 0)

    def get_condenser_temp(self, time_slot: DateTime) -> float:
        """Return the condenser temperature for a given time slot."""
        return self._condenser_temp_C.get(time_slot, 0)

    def get_state(self) -> Dict:
        return {
            "energy_consumption_kWh": convert_pendulum_to_str_in_dict(
                self._energy_consumption_kWh
            ),
            "min_energy_demand_kWh": convert_pendulum_to_str_in_dict(self._min_energy_demand_kWh),
            "max_energy_demand_kWh": convert_pendulum_to_str_in_dict(self._max_energy_demand_kWh),
            "cop": convert_pendulum_to_str_in_dict(self._cop),
            "condenser_temp_C": convert_pendulum_to_str_in_dict(self._condenser_temp_C),
            "heat_demand_kJ": convert_pendulum_to_str_in_dict(self._heat_demand_kJ),
            "total_traded_energy_kWh": self._total_traded_energy_kWh,
        }

    def restore_state(self, state_dict: Dict):
        self._energy_consumption_kWh = convert_str_to_pendulum_in_dict(
            state_dict["energy_consumption_kWh"]
        )
        self._min_energy_demand_kWh = convert_str_to_pendulum_in_dict(
            state_dict["min_energy_demand_kWh"]
        )
        self._max_energy_demand_kWh = convert_str_to_pendulum_in_dict(
            state_dict["max_energy_demand_kWh"]
        )
        self._cop = convert_str_to_pendulum_in_dict(state_dict["cop"])
        self._heat_demand_kJ = convert_str_to_pendulum_in_dict(state_dict["heat_demand_kJ"])
        self._condenser_temp_C = convert_str_to_pendulum_in_dict(state_dict["condenser_temp_C"])
        self._total_traded_energy_kWh = state_dict["total_traded_energy_kWh"]

    def delete_past_state_values(self, current_time_slot: DateTime):
        if not current_time_slot or constants.RETAIN_PAST_MARKET_STRATEGIES_STATE:
            return
        last_time_slot = self._last_time_slot(current_time_slot)
        self._delete_time_slots(self._min_energy_demand_kWh, last_time_slot)
        self._delete_time_slots(self._max_energy_demand_kWh, last_time_slot)
        self._delete_time_slots(self._energy_consumption_kWh, last_time_slot)
        self._delete_time_slots(self._cop, last_time_slot)
        self._delete_time_slots(self._condenser_temp_C, last_time_slot)
        self._delete_time_slots(self._heat_demand_kJ, last_time_slot)

    def get_results_dict(self, current_time_slot: DateTime) -> Dict:
        retval = {
            "energy_consumption_kWh": self.get_energy_consumption_kWh(current_time_slot),
            "max_energy_demand_kWh": self.get_max_energy_demand_kWh(current_time_slot),
            "min_energy_demand_kWh": self.get_min_energy_demand_kWh(current_time_slot),
            "cop": self.get_cop(current_time_slot),
            "total_traded_energy_kWh": self._total_traded_energy_kWh,
            "heat_demand_kJ": self.get_heat_demand_kJ(current_time_slot),
        }
        return retval

    def __str__(self):
        return self.__class__.__name__
