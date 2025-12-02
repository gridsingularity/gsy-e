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

from typing import Optional, Dict, List

from pendulum import DateTime, duration

from gsy_framework.constants_limits import ConstSettings, DATE_TIME_FORMAT
from gsy_framework.enums import EVChargerStatus

from gsy_e.models.strategy.state.storage_state import (
    StorageState,
    ESSEnergyOrigin,
    StorageLosses,
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

        # Internal state tracking for the session
        self._current_soc_percent = initial_soc_percent
        self._current_energy_kWh = (initial_soc_percent / 100.0) * battery_capacity_kWh

    @property
    def session_id(self) -> str:
        """Generate a unique identifier for this charging session."""
        start_str = self.plug_in_time.format(DATE_TIME_FORMAT)
        return f"EV-PLUG{start_str}-CAP{int(self.battery_capacity_kWh)}kWh-{id(self)}"

    @property
    def end_time(self) -> DateTime:
        """Calculate session end time."""
        return self.plug_in_time.add(minutes=self.duration_minutes)

    def is_active(self, time_slot: DateTime) -> bool:
        """Check if session is active at given time slot."""
        return self.plug_in_time <= time_slot < self.end_time

    @property
    def current_soc_percent(self) -> float:
        """Get current state of charge percentage."""
        return self._current_soc_percent

    @property
    def current_energy_kWh(self) -> float:
        """Get current stored energy in kWh."""
        return self._current_energy_kWh

    def get_available_energy_to_buy_kWh(self, max_power_kW: float, slot_length: duration) -> float:
        """Calculate available energy to buy for this session."""
        # Energy based on power rating and slot length
        max_energy_from_power = max_power_kW * (slot_length / duration(hours=1))

        # Energy based on remaining capacity
        max_capacity = self.battery_capacity_kWh
        current_energy = self._current_energy_kWh
        available_capacity = max_capacity - current_energy

        return min(max_energy_from_power, available_capacity)

    def get_available_energy_to_sell_kWh(
        self, max_power_kW: float, slot_length: duration
    ) -> float:
        """Calculate available energy to sell for this session."""
        # Energy based on power rating and slot length
        max_energy_from_power = max_power_kW * (slot_length / duration(hours=1))

        # Energy based on available stored energy above minimum SOC
        min_energy = (self.min_soc_percent / 100.0) * self.battery_capacity_kWh
        available_energy = max(0, self._current_energy_kWh - min_energy)

        return min(max_energy_from_power, available_energy)

    def add_energy(self, energy_kWh: float):
        """Add bought energy to the session."""
        self._current_energy_kWh += energy_kWh
        self._current_soc_percent = (self._current_energy_kWh / self.battery_capacity_kWh) * 100.0

    def remove_energy(self, energy_kWh: float):
        """Remove sold energy from the session."""
        self._current_energy_kWh -= energy_kWh
        self._current_soc_percent = (self._current_energy_kWh / self.battery_capacity_kWh) * 100.0


class EVSessionsManager:
    """Manages multiple concurrent EV charging sessions."""

    def __init__(
        self,
        sessions: List[EVChargingSession],
        slot_length: duration,
        losses: StorageLosses,
    ):
        self.sessions = sessions
        self.slot_length = slot_length
        self.losses = losses

    def get_active_sessions(self, time_slot: DateTime) -> List[EVChargingSession]:
        """Get all sessions active at the given time slot."""
        return [session for session in self.sessions if session.is_active(time_slot)]

    def get_aggregate_energy_to_buy_kWh(self, time_slot: DateTime, max_power_kW: float) -> float:
        """
        Calculate aggregate energy to buy across all active sessions.
        Sessions are limited by the provided max power rating.
        """
        active_sessions = self.get_active_sessions(time_slot)
        if not active_sessions:
            return 0.0

        # Sum up energy requirements from all sessions
        total_energy_needed = sum(
            session.get_available_energy_to_buy_kWh(max_power_kW, self.slot_length)
            for session in active_sessions
        )

        return total_energy_needed

    def get_aggregate_energy_to_sell_kWh(self, time_slot: DateTime, max_power_kW: float) -> float:
        """
        Calculate aggregate energy to sell across all active sessions.
        Sessions are limited by the provided max power rating.
        """
        active_sessions = self.get_active_sessions(time_slot)
        if not active_sessions:
            return 0.0

        # Sum up energy available from all sessions
        total_energy_available = sum(
            session.get_available_energy_to_sell_kWh(max_power_kW, self.slot_length)
            for session in active_sessions
        )

        return total_energy_available

    def distribute_bought_energy(
        self, time_slot: DateTime, total_energy_bought_kWh: float
    ) -> Dict[str, float]:
        """
        Distribute bought energy proportionally to SOC levels of active sessions.
        EVs with lower SOC receive more energy.

        Weighting: Uses inverse SOC (100 - SOC), so lower SOC gets higher priority.
        If all sessions are at 100% SOC, energy is distributed equally.
        Charging losses are applied before distribution to sessions.
        """
        active_sessions = self.get_active_sessions(time_slot)
        if not active_sessions:
            return {}

        effective_energy = total_energy_bought_kWh * (1.0 - self.losses.charging_loss_percent)

        weights = {
            session.session_id: (100.0 - session.current_soc_percent)
            for session in active_sessions
        }
        total_weight = sum(weights.values())

        if total_weight == 0:
            energy_per_session = effective_energy / len(active_sessions)
            distribution = {session.session_id: energy_per_session for session in active_sessions}
        else:
            distribution = {
                session.session_id: effective_energy * (weights[session.session_id] / total_weight)
                for session in active_sessions
            }

        for session in active_sessions:
            energy = distribution[session.session_id]
            session.add_energy(energy)

        return distribution

    def distribute_sold_energy(
        self, time_slot: DateTime, total_energy_sold_kWh: float
    ) -> Dict[str, float]:
        """
        Distribute sold energy proportionally to SOC levels of active sessions.
        EVs with higher SOC contribute more energy.

        Weighting: Uses SOC above minimum (higher SOC = more contribution).
        If all sessions are at minimum SOC, no energy can be distributed.
        Discharging losses are applied after energy removal from sessions.
        """
        active_sessions = self.get_active_sessions(time_slot)
        if not active_sessions:
            return {}

        weights = {
            session.session_id: max(0, session.current_soc_percent - session.min_soc_percent)
            for session in active_sessions
        }
        total_weight = sum(weights.values())

        if total_weight == 0:
            return {}

        distribution = {
            session.session_id: total_energy_sold_kWh
            * (weights[session.session_id] / total_weight)
            for session in active_sessions
        }

        for session in active_sessions:
            energy = distribution[session.session_id]
            session.remove_energy(energy)

        for session_id in distribution:
            distribution[session_id] *= 1.0 - self.losses.discharging_loss_percent

        return distribution


# pylint: disable= too-many-instance-attributes, too-many-arguments, too-many-public-methods
class EVChargerState(StorageState):
    """State for the EV charger asset."""

    def __init__(
        self,
        maximum_power_rating_kW: float,
        losses: StorageLosses,
        charging_sessions: List[EVChargingSession] = None,
        preferred_power_profile: dict = None,
        slot_length: duration = None,
    ):
        self.maximum_power_rating_kW = maximum_power_rating_kW
        self._preferred_power_profile = preferred_power_profile
        self._slot_length = slot_length
        self._losses = losses
        sessions = charging_sessions or []

        self.ev_sessions_manager = EVSessionsManager(
            sessions=sessions,
            slot_length=slot_length,
            losses=losses,
        )

        # dummy initialization of base storage
        super().__init__(
            initial_soc=0,
            capacity=0,
            max_abs_battery_power_kW=0,
            min_allowed_soc=0,
            initial_energy_origin=ESSEnergyOrigin.EXTERNAL,
            losses=losses,
        )

    @property
    def used_storage(self) -> float:
        """Return total stored energy across all sessions."""
        return sum(session.current_energy_kWh for session in self.ev_sessions_manager.sessions)

    def update_sessions(self, sessions: List[EVChargingSession]) -> None:
        """Update the charging sessions managed by this state."""
        self.ev_sessions_manager.sessions = sessions

    def has_active_sessions(self, time_slot: DateTime) -> bool:
        """Check if there are any active sessions at the given time slot."""
        return len(self.ev_sessions_manager.get_active_sessions(time_slot)) > 0

    def check_state(self, time_slot):
        """Skip SOC sanity check for EV chargers (they can start below min SOC)."""

    def _clamp_energy_to_sell_kWh(self, market_slot_time_list):
        """
        Determines available energy to sell for each active market.
        For EV chargers, delegates to get_available_energy_to_sell_kWh for each time slot.
        """
        storage_dict = {}
        for time_slot in market_slot_time_list:
            storage_dict[time_slot] = self.get_available_energy_to_sell_kWh(time_slot)
        return storage_dict

    def get_results_dict(self, current_time_slot):
        """Return EV charger state summary for results reporting."""
        active_sessions = self.ev_sessions_manager.get_active_sessions(current_time_slot)

        if not active_sessions:
            return {
                "status": EVChargerStatus.IDLE,
            }

        total_energy = sum(session.current_energy_kWh for session in active_sessions)
        soc_values = [session.current_soc_percent for session in active_sessions]
        min_soc = min(soc_values)
        max_soc = max(soc_values)

        return {
            "status": EVChargerStatus.ACTIVE,
            "active_sessions_count": len(active_sessions),
            "total_stored_energy_kWh": total_energy,
            "min_soc_%": min_soc,
            "max_soc_%": max_soc,
            "sessions": [
                {
                    "session_id": session.session_id,
                    "soc_%": session.current_soc_percent,
                    "energy_kWh": session.current_energy_kWh,
                }
                for session in active_sessions
            ],
        }

    def _get_preferred_power_for_slot(self, time_slot: DateTime) -> Optional[float]:
        """
        Get the preferred power value for the given time slot.
        """
        if self._preferred_power_profile is None:
            return None

        if time_slot in self._preferred_power_profile:
            return self._preferred_power_profile[time_slot]

        return None

    def _convert_power_to_energy(self, power_kW: float) -> float:
        """Convert power (kW) to energy (kWh) based on slot length for the given time slot."""
        if self._slot_length is None:
            return 0.0
        return power_kW * (self._slot_length / duration(hours=1))

    def get_available_energy_to_buy_kWh(self, time_slot: DateTime) -> float:
        """
        Get aggregated energy to buy across all active sessions.
        Respects maximum power rating and preferred charging power limit if configured.
        """
        preferred_power_kW = self._get_preferred_power_for_slot(time_slot)

        if preferred_power_kW is not None and preferred_power_kW < 0:
            return 0.0  # preferred power is discharging

        if preferred_power_kW is not None and preferred_power_kW >= 0:
            effective_max_power_kW = preferred_power_kW
        else:
            effective_max_power_kW = self.maximum_power_rating_kW

        aggregate_energy = self.ev_sessions_manager.get_aggregate_energy_to_buy_kWh(
            time_slot, effective_max_power_kW
        )
        max_energy_from_charger = self.maximum_power_rating_kW * (
            self._slot_length / duration(hours=1)
        )
        energy_to_buy = min(aggregate_energy, max_energy_from_charger)

        return energy_to_buy

    def get_available_energy_to_sell_kWh(self, time_slot: DateTime) -> float:
        """
        Get aggregated energy to sell across all active sessions.
        Respects maximum power rating and preferred charging power limit if configured.
        """
        preferred_power_kW = self._get_preferred_power_for_slot(time_slot)

        if preferred_power_kW is not None and preferred_power_kW >= 0:
            return 0.0  # preferred power is charging/neutral

        if preferred_power_kW is not None and preferred_power_kW < 0:
            effective_max_power_kW = abs(preferred_power_kW)
        else:
            effective_max_power_kW = self.maximum_power_rating_kW

        aggregate_energy = self.ev_sessions_manager.get_aggregate_energy_to_sell_kWh(
            time_slot, effective_max_power_kW
        )
        max_energy_from_charger = self.maximum_power_rating_kW * (
            self._slot_length / duration(hours=1)
        )
        energy_to_sell = min(aggregate_energy, max_energy_from_charger)

        return energy_to_sell
