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

from math import isclose
from typing import Optional, Dict, List

from pendulum import DateTime, duration

from gsy_framework.constants_limits import ConstSettings, FLOATING_POINT_TOLERANCE
from gsy_framework.enums import EVChargerStatus
from gsy_framework.utils import convert_kW_to_kWh, limit_float_precision

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
        return f"EV-{id(self)}-CAP{int(self.battery_capacity_kWh)}"

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

    def has_active_sessions(self, time_slot: DateTime) -> bool:
        """Check if there are any active sessions at the given time slot."""
        return len(self.get_active_sessions(time_slot)) > 0

    def get_total_capacity_kWh(self, time_slot: DateTime) -> float:
        """Get total battery capacity for all active sessions at given time slot."""
        active_sessions = self.get_active_sessions(time_slot)
        return sum(session.battery_capacity_kWh for session in active_sessions)

    def get_total_energy_kWh(self, time_slot: DateTime) -> float:
        """Get total stored energy across all active sessions at given time slot."""
        active_sessions = self.get_active_sessions(time_slot)
        return sum(session.current_energy_kWh for session in active_sessions)

    def get_aggregate_energy_to_buy_kWh(self, time_slot: DateTime, max_power_kW: float) -> float:
        """
        Calculate aggregate energy demand across all active sessions.
        Returns the total energy needed by all sessions combined (not limited by charger power).
        The charger power limit is applied afterwards at the EVChargerState level.
        """
        active_sessions = self.get_active_sessions(time_slot)
        if not active_sessions:
            return 0.0

        # Each session reports remaining capacity, ignoring the power constraint
        total_energy_needed = sum(
            session.battery_capacity_kWh - session.current_energy_kWh
            for session in active_sessions
        )

        return total_energy_needed

    def get_aggregate_energy_to_sell_kWh(self, time_slot: DateTime, max_power_kW: float) -> float:
        """
        Calculate aggregate energy available to sell across all active sessions.
        Returns the total energy available from all sessions combined (not limited
        by charger power). The charger power limit is applied afterward at the
        EVChargerState level.
        """
        active_sessions = self.get_active_sessions(time_slot)
        if not active_sessions:
            return 0.0

        # Each session reports what it can provide, ignoring the power constraint
        total_energy_available = 0.0
        for session in active_sessions:
            min_energy = (session.min_soc_percent / 100.0) * session.battery_capacity_kWh
            available_energy = max(0, session.current_energy_kWh - min_energy)
            total_energy_available += available_energy

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

    def check_state(self, time_slot):
        """
        Validate state for EV chargers with concurrent sessions.
        Based on StorageState.check_state() but adapted for dynamic capacity.
        Reference: storage_state.py lines 274-295
        """
        # Clamp energy to realistic bounds based on active sessions
        self._clamp_energy_to_sell_kWh([time_slot])
        self._clamp_energy_to_buy_kWh([time_slot])

        # Note: _calculate_and_update_soc() not needed - each EV session tracks its own SOC
        # Storage uses charge_history dict, but EV sessions track SOC individually

        if not self.ev_sessions_manager.has_active_sessions(time_slot):
            return

        # Validate total energy doesn't exceed total capacity across all sessions
        total_capacity_kWh = self.ev_sessions_manager.get_total_capacity_kWh(time_slot)
        total_energy_kWh = self.ev_sessions_manager.get_total_energy_kWh(time_slot)

        assert limit_float_precision(total_energy_kWh) <= total_capacity_kWh or isclose(
            total_energy_kWh, total_capacity_kWh, rel_tol=1e-06
        ), (
            f"Total EV energy ({total_energy_kWh} kWh) exceeds total capacity "
            f"({total_capacity_kWh} kWh)"
        )

        # Validate pledged/offered energy is within reasonable bounds
        # Unlike storage, we use total_capacity_kWh which is dynamic based on active sessions
        max_value_kWh = total_capacity_kWh
        assert 0 <= limit_float_precision(self.offered_sell_kWh[time_slot]) <= max_value_kWh
        assert 0 <= limit_float_precision(self.pledged_sell_kWh[time_slot]) <= max_value_kWh
        assert 0 <= limit_float_precision(self.pledged_buy_kWh[time_slot]) <= max_value_kWh
        assert 0 <= limit_float_precision(self.offered_buy_kWh[time_slot]) <= max_value_kWh

    def _clamp_energy_to_buy_kWh(self, market_slot_time_list):
        """
        Override to handle dynamic capacity based on active EV sessions.
        Based on StorageState._clamp_energy_to_buy_kWh() but uses dynamic capacity.
        Reference: storage_state.py lines 243-268
        Key difference: Uses total_capacity_kWh per slot instead of static self.capacity
        """
        accumulated_bought = 0
        accumulated_sought = 0
        for time_slot, offered_buy_energy in self.offered_buy_kWh.items():
            if time_slot >= self._current_market_slot:
                accumulated_bought += self.pledged_buy_kWh[time_slot]
                accumulated_sought += offered_buy_energy

        for time_slot in market_slot_time_list:
            total_capacity_kWh = self.ev_sessions_manager.get_total_capacity_kWh(time_slot)
            available_energy_for_slot = limit_float_precision(
                total_capacity_kWh - self.used_storage - accumulated_bought - accumulated_sought
            )

            if available_energy_for_slot < -FLOATING_POINT_TOLERANCE:
                self.energy_to_buy_dict[time_slot] = 0
                continue

            available_energy_kWh = self.get_available_energy_to_buy_kWh(time_slot)
            clamped_energy = limit_float_precision(
                min(available_energy_for_slot, available_energy_kWh)
            )
            clamped_energy = max(clamped_energy, 0)
            self.energy_to_buy_dict[time_slot] = clamped_energy
            accumulated_bought += clamped_energy

    def _clamp_energy_to_sell_kWh(self, market_slot_time_list):
        """
        Override to handle dynamic capacity and skip min SOC for EV sessions.
        Based on StorageState._clamp_energy_to_sell_kWh() but without min_allowed_soc_ratio.
        Reference: storage_state.py lines 210-240
        Key difference: Skips min_allowed_soc_ratio * capacity term since each EV session
        handles its own min_soc_percent constraint in get_aggregate_energy_to_sell_kWh()
        """
        accumulated_pledged = 0
        accumulated_offered = 0
        for time_slot, offered_sell_energy in self.offered_sell_kWh.items():
            if time_slot >= self._current_market_slot:
                accumulated_pledged += self.pledged_sell_kWh[time_slot]
                accumulated_offered += offered_sell_energy

        # Skip min_allowed_soc_ratio * capacity term since EVs can start below min SOC
        available_energy_for_all_slots = (
            self.used_storage - accumulated_pledged - accumulated_offered
        )

        storage_dict = {}
        for time_slot in market_slot_time_list:
            if available_energy_for_all_slots < -FLOATING_POINT_TOLERANCE:
                break

            available_energy_kWh = self.get_available_energy_to_sell_kWh(time_slot)
            storage_dict[time_slot] = limit_float_precision(
                min(available_energy_for_all_slots, available_energy_kWh)
            )
            self.energy_to_sell_dict[time_slot] = storage_dict[time_slot]
            available_energy_for_all_slots -= storage_dict[time_slot]
        return storage_dict

    def get_results_dict(self, current_time_slot):
        """Return EV charger state summary for results reporting."""
        # Handle case when current_time_slot is None (simulation not started or ended)
        if current_time_slot is None:
            return {
                "status": EVChargerStatus.IDLE,
            }

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

        return self._preferred_power_profile.get(time_slot)

    def _get_effective_power_kW(self, time_slot: DateTime, is_buying: bool) -> Optional[float]:
        """
        Get effective power limit for buying or selling based on preferred power profile.
        """
        preferred_power_kW = self._get_preferred_power_for_slot(time_slot)

        if preferred_power_kW is None:
            return self.maximum_power_rating_kW

        if is_buying:
            if preferred_power_kW < 0:
                return None  # Discharging - can't buy
            return preferred_power_kW
        else:
            if preferred_power_kW >= 0:
                return None  # Charging/neutral - can't sell
            return abs(preferred_power_kW)

    def get_available_energy_to_buy_kWh(self, time_slot: DateTime) -> float:
        """
        Get aggregated energy to buy across all active sessions.
        Respects maximum power rating and preferred charging power limit if configured.
        Returns clamped value that accounts for already-posted bids.
        """
        # Prevent buying more if we've already traded for this slot
        if time_slot in self.pledged_buy_kWh and self.pledged_buy_kWh[time_slot] > 0:
            return 0.0

        effective_power_kW = self._get_effective_power_kW(time_slot, is_buying=True)
        if effective_power_kW is None:
            return 0.0

        aggregate_energy = self.ev_sessions_manager.get_aggregate_energy_to_buy_kWh(
            time_slot, effective_power_kW
        )
        max_energy_kWh = convert_kW_to_kWh(effective_power_kW, self._slot_length)

        return min(aggregate_energy, max_energy_kWh)

    def get_available_energy_to_sell_kWh(self, time_slot: DateTime) -> float:
        """
        Get aggregated energy to sell across all active sessions.
        Respects maximum power rating and preferred charging power limit if configured.
        Returns clamped value that accounts for already-posted offers.
        """
        # Prevent selling more if we've already traded for this slot
        if time_slot in self.pledged_sell_kWh and self.pledged_sell_kWh[time_slot] > 0:
            return 0.0

        effective_power_kW = self._get_effective_power_kW(time_slot, is_buying=False)
        if effective_power_kW is None:
            return 0.0

        aggregate_energy = self.ev_sessions_manager.get_aggregate_energy_to_sell_kWh(
            time_slot, effective_power_kW
        )
        max_energy_kWh = convert_kW_to_kWh(effective_power_kW, self._slot_length)

        return min(aggregate_energy, max_energy_kWh)
