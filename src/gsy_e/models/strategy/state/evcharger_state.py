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

from typing import Optional

from pendulum import DateTime, duration

from gsy_framework.constants_limits import ConstSettings, DATE_TIME_FORMAT
from gsy_framework.enums import EVChargerStatus
from gsy_framework.utils import get_from_profile_same_weekday_and_time

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
        start_str = self.plug_in_time.format(DATE_TIME_FORMAT)
        return f"EV-PLUG{start_str}-CAP{int(self.battery_capacity_kWh)}kWh"


# pylint: disable= too-many-instance-attributes, too-many-arguments, too-many-public-methods
class EVChargerState(StorageState):
    """State for the EV charger asset."""

    def __init__(
        self,
        maximum_power_rating_kW: float,
        preferred_power_profile: dict = None,
        slot_length: duration = None,
    ):
        self.maximum_power_rating_kW = maximum_power_rating_kW
        self.active_charging_session = None
        self._preferred_power_profile = preferred_power_profile
        self._slot_length = slot_length

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

    def _get_preferred_power_for_slot(self, time_slot: DateTime) -> Optional[float]:
        """
        Get the preferred power value for the given time slot.
        """
        if self._preferred_power_profile is None:
            return None

        if time_slot in self._preferred_power_profile:
            return self._preferred_power_profile[time_slot]

        # For canary network, try weekday/time matching
        if ConstSettings.GeneralSettings.IS_CANARY_NETWORK:
            return get_from_profile_same_weekday_and_time(
                self._preferred_power_profile, time_slot, ignore_not_found=True
            )

        return None

    def _convert_power_to_energy(self, power_kW: float, time_slot: DateTime) -> float:
        """Convert power (kW) to energy (kWh) based on slot length for the given time slot."""
        if self._slot_length is None:
            return 0.0
        return power_kW * (self._slot_length / duration(hours=1))

    def get_available_energy_to_buy_kWh(self, time_slot: DateTime) -> float:
        """
        Override to use preferred charging power when configured.

        Positive preferred power = charging (buy energy from grid)
        Negative preferred power = discharging (handled by sell logic)
        """
        preferred_power_kW = self._get_preferred_power_for_slot(time_slot)

        if preferred_power_kW is None:
            # No preferred power set, use default storage behavior
            return super().get_available_energy_to_buy_kWh(time_slot)

        # Only buy if positive (charging mode)
        energy_kWh = self._convert_power_to_energy(preferred_power_kW, time_slot)
        if energy_kWh > 0:
            max_energy_to_buy = super().get_available_energy_to_buy_kWh(time_slot)
            return min(energy_kWh, max_energy_to_buy)

        return 0.0

    def get_available_energy_to_sell_kWh(self, time_slot: DateTime) -> float:
        """
        Override to use preferred charging power when configured.

        Negative preferred power = discharging (sell energy to grid)
        Positive preferred power = charging (handled by buy logic)
        """
        preferred_power_kW = self._get_preferred_power_for_slot(time_slot)

        if preferred_power_kW is None or preferred_power_kW >= 0:
            # No preferred power or it's positive (charging), use default storage behavior
            return super().get_available_energy_to_sell_kWh(time_slot)

        # Convert negative power (discharging) to positive energy to sell
        energy_kWh = abs(self._convert_power_to_energy(preferred_power_kW, time_slot))
        max_energy_to_sell = super().get_available_energy_to_sell_kWh(time_slot)
        return min(energy_kWh, max_energy_to_sell)
