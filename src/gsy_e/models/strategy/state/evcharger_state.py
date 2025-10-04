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

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import GridIntegrationType

from gsy_e.models.strategy.state.storage_state import (
    StorageState,
    ESSEnergyOrigin,
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
        grid_integration: GridIntegrationType,
        maximum_power_rating_kW: float,
        active_charging_session: EVChargingSession,
    ):
        super().__init__(
            initial_soc=active_charging_session.initial_soc_percent,
            capacity=active_charging_session.battery_capacity_kWh,
            max_abs_battery_power_kW=maximum_power_rating_kW,
            min_allowed_soc=active_charging_session.min_soc_percent,
            initial_energy_origin=ESSEnergyOrigin.EXTERNAL,
        )
        self.active_charging_session = active_charging_session
        self.grid_integration = grid_integration

    def get_results_dict(self):
        return {
            "grid_integration": self.grid_integration,
            "session_start": self.active_charging_session.plug_in_time,
            "session_duration": self.active_charging_session.duration_minutes,
        }

    def check_state(self, time_slot):
        """Skip SOC sanity check for EV chargers (they can start below min SOC)."""
        # reuse parent checks but skip the min SOC assertion
        self._clamp_energy_to_sell_kWh([time_slot])
        self._clamp_energy_to_buy_kWh([time_slot])
        self._calculate_and_update_soc(time_slot)
