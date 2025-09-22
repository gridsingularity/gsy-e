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

from typing import Dict, List, Optional
from pendulum import DateTime
from math import isclose

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import GridIntegrationType
from gsy_framework.utils import convert_kW_to_kWh, limit_float_precision

from gsy_e.gsy_e_core.util import write_default_to_dict
from gsy_e.models.strategy.state.base_states import StateInterface
from gsy_e.models.strategy.state.storage_state import (
    StorageSettings,
    StorageState,
    ESSEnergyOrigin,
    EnergyOrigin,
)

EVChargerSettings = ConstSettings.EVChargerSettings


class EVChargingSession:
    """Class to represent an EV charging/discharging session."""

    def __init__(
        self,
        plug_in_time: str,
        duration_minutes: int,
        initial_soc_percent: float = 20.0,
        min_soc_percent: float = 50.0,
        battery_capacity_kWh: float = 100.0,
    ):
        self.plug_in_time = plug_in_time
        self.duration_minutes = duration_minutes
        self.initial_soc_percent = initial_soc_percent
        self.min_soc_percent = min_soc_percent
        self.battery_capacity_kWh = battery_capacity_kWh


# pylint: disable= too-many-instance-attributes, too-many-arguments, too-many-public-methods
class EVChargerState(StorageState):
    """State for the EV charger asset."""

    def __init__(
        self,
        active_charging_session: EVChargingSession,
        grid_integration: Optional[GridIntegrationType] = None,
        max_abs_battery_power_kW=EVChargerSettings.MAX_POWER_RATING_KW,
        initial_soc=StorageSettings.MIN_ALLOWED_SOC,
        capacity=StorageSettings.CAPACITY,
        initial_energy_origin=ESSEnergyOrigin.EXTERNAL,
    ):
        self.active_charging_session = active_charging_session
        self.grid_integration = grid_integration
        self.max_abs_battery_power_kW = max_abs_battery_power_kW
        self.initial_soc = initial_soc
        self.initial_capacity_kWh = capacity * initial_soc / 100
        self.capacity = capacity

        # storage capacity, that is already sold:
        self.pledged_sell_kWh = {}
        # storage capacity, that has been offered (but not traded yet):
        self.offered_sell_kWh = {}
        # energy, that has been bought:
        self.pledged_buy_kWh = {}
        # energy, that the storage wants to buy (but not traded yet):
        self.offered_buy_kWh = {}
        self.time_series_ess_share = {}

        self.charge_history = {}
        self.charge_history_kWh = {}

        self.offered_history = {}
        self.energy_to_buy_dict = {}
        self.energy_to_sell_dict = {}

        self._used_storage = self.initial_capacity_kWh
        self._battery_energy_per_slot = 0.0
        self.initial_energy_origin = initial_energy_origin
        self._used_storage_share = [EnergyOrigin(initial_energy_origin, self.initial_capacity_kWh)]
        self._current_market_slot = None

    def get_state(self):
        return {"grid_integration": self.grid_integration}

    def restore_state(self, state):
        self.grid_integration = state.get("grid_integration")

    def delete_past_state_values(self, market_time_slot):
        pass

    def get_results_dict(self):
        return {"grid_integration": self.grid_integration}

    def activate(self, slot_length: int, current_time_slot: DateTime) -> None:
        """Set the battery energy in kWh per current time_slot."""
        self._battery_energy_per_slot = convert_kW_to_kWh(
            self.max_abs_battery_power_kW, slot_length
        )
        self._current_market_slot = current_time_slot

    def check_state(self, time_slot):
        """
        Sanity check of the state variables.
        """
        assert True

    def add_default_values_to_state_profiles(self, future_time_slots: List):
        """Add default values to the state profiles if time_slot key doesn't exist."""
        for time_slot in future_time_slots:
            write_default_to_dict(self.pledged_sell_kWh, time_slot, 0)
            write_default_to_dict(self.pledged_buy_kWh, time_slot, 0)
            write_default_to_dict(self.offered_sell_kWh, time_slot, 0)
            write_default_to_dict(self.offered_buy_kWh, time_slot, 0)

            write_default_to_dict(self.charge_history, time_slot, self.initial_soc)
            write_default_to_dict(self.charge_history_kWh, time_slot, self.initial_capacity_kWh)

            write_default_to_dict(self.energy_to_buy_dict, time_slot, 0)
            write_default_to_dict(self.energy_to_sell_dict, time_slot, 0)
            write_default_to_dict(self.offered_history, time_slot, "-")
