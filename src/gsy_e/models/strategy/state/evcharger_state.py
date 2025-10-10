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
from gsy_framework.enums import EVChargerStatus

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

    @property
    def session_id(self) -> str:
        """Generate a short, human-readable identifier."""
        start_str = self.plug_in_time.format("YYYYMMDDHHmm")
        return f"EV-PLUG{start_str}-CAP{int(self.battery_capacity_kWh)}kWh"


# pylint: disable= too-many-instance-attributes, too-many-arguments, too-many-public-methods
class EVChargerState(StorageState):
    """State for the EV charger asset."""

    def __init__(
        self,
        maximum_power_rating_kW: float,
    ):
        self.maximum_power_rating_kW = maximum_power_rating_kW
        self.active_charging_session = None

        # dummy initialization of base storage
        super().__init__(
            initial_soc=0,
            capacity=0,
            max_abs_battery_power_kW=0,
            min_allowed_soc=0,
            initial_energy_origin=ESSEnergyOrigin.EXTERNAL,
        )

    def reinitialize(self, session: EVChargingSession):
        """Reinitialize the storage strategy state when a session becomes active."""
        self.active_charging_session = session

        super().__init__(
            initial_soc=session.initial_soc_percent,
            capacity=session.battery_capacity_kWh,
            max_abs_battery_power_kW=self.maximum_power_rating_kW,
            min_allowed_soc=session.min_soc_percent,
            initial_energy_origin=ESSEnergyOrigin.EXTERNAL,
        )

    def reset(self):
        """Resets the state of the EV charger by clearing the active charging session."""
        self.active_charging_session = None

    def check_state(self, time_slot):
        """Skip SOC sanity check for EV chargers (they can start below min SOC)."""
        # reuse parent checks but skip the min SOC assertion
        self._clamp_energy_to_sell_kWh([time_slot])
        self._clamp_energy_to_buy_kWh([time_slot])
        self._calculate_and_update_soc(time_slot)

    def get_results_dict(self, current_time_slot):
        """Return EV charger state summary for results reporting."""
        if not getattr(self, "active_charging_session", None):
            return {
                "status": EVChargerStatus.IDLE,
            }

        return {
            "status": EVChargerStatus.ACTIVE,
            "used_storage_kWh": getattr(self, "used_storage", 0.0),
            "soc_history_%": self.charge_history.get(current_time_slot, 0.0),
        }
