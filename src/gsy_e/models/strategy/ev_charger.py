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

from logging import getLogger
from typing import Optional, Union, Dict

from pendulum import DateTime
from gsy_framework.validators import EVChargerValidator
from gsy_framework.enums import GridIntegrationType, EVChargerStatus
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.read_user_profile import UserProfileReader, InputProfileTypes

from gsy_e.models.strategy.state.evcharger_state import EVChargerState, EVChargingSession
from gsy_e.models.strategy.storage import StorageStrategy

log = getLogger(__name__)


EVChargerSettings = ConstSettings.EVChargerSettings
StorageSettings = ConstSettings.StorageSettings


class EVChargerStrategy(StorageStrategy):
    """Strategy class EV Charger. Similar to StorageStrategy but only during active sessions."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        grid_integration: GridIntegrationType = GridIntegrationType.BIDIRECTIONAL,
        charging_sessions: list[EVChargingSession] = [],
        maximum_power_rating_kW: float = ConstSettings.EVChargerSettings.MAX_POWER_RATING_KW,
        preferred_charging_power: Optional[Union[float, Dict[DateTime, float]]] = None,
        **kwargs,
    ):
        """
        Args:
             grid_integration: connection between the grid and EVs
             preferred_charging_power: User-specified charging power (kW) per market slot that
                replaces default strategy. Can be a constant value or time-based profile.
        """
        EVChargerValidator.validate(
            grid_integration=grid_integration,
            maximum_power_rating_kW=maximum_power_rating_kW,
            preferred_charging_power=preferred_charging_power,
        )

        super().__init__(**kwargs)

        self.grid_integration = grid_integration
        self.maximum_power_rating_kW = maximum_power_rating_kW
        self.preferred_charging_power = preferred_charging_power
        self.charging_sessions = sorted(charging_sessions, key=lambda s: s.plug_in_time)
        self.active_session_index: Optional[int] = None
        self.status = EVChargerStatus.IDLE

        # Convert preferred_charging_power to profile if provided
        preferred_power_profile = None
        if preferred_charging_power is not None:
            preferred_power_profile = UserProfileReader().read_arbitrary_profile(
                InputProfileTypes.IDENTITY, preferred_charging_power
            )

        self._state = EVChargerState(
            maximum_power_rating_kW=self.maximum_power_rating_kW,
            preferred_power_profile=preferred_power_profile,
            slot_length=GlobalConfig.slot_length,
        )

    @property
    def state(self) -> EVChargerState:
        return self._state

    def _maybe_update_session(self, now: DateTime) -> bool:
        """Switch StorageStrategy state when entering a new session."""
        active_session = None
        for idx, charging_session in enumerate(self.charging_sessions):
            start = charging_session.plug_in_time
            end = start.add(minutes=charging_session.duration_minutes)

            if start <= now < end:
                active_session = charging_session

                if self.active_session_index != idx:
                    # switch session
                    self.active_session_index = idx
                    self._state.reinitialize(active_session)
                    self._update_profiles_with_default_values()
                    self._state.activate(self.simulation_config.slot_length, now)
                    self._state.add_default_values_to_state_profiles([now])
                    self.status = EVChargerStatus.ACTIVE
                return True

        if active_session is None and self.status == EVChargerStatus.ACTIVE:
            self.active_session_index = None
            self._state.reset()
            self.status = EVChargerStatus.IDLE
        return False

    def event_activate(self, **kwargs):
        now = self.area.spot_market.time_slot

        self._maybe_update_session(now)
        if self.status == EVChargerStatus.IDLE:
            return  # skip StorageStrategy activation when no session active
        super().event_activate(**kwargs)

    def event_market_cycle(self):
        now = self.area.spot_market.time_slot

        if not self._maybe_update_session(now):
            return  # skip if we are in an active charging session
        super().event_market_cycle()

    def event_tick(self):
        now = self.area.spot_market.time_slot

        if not self._maybe_update_session(now):
            return  # skip if we are in an active charging session
        super().event_tick()

    def _sell_energy_to_spot_market(self):
        if self.grid_integration == GridIntegrationType.UNIDIRECTIONAL:
            return  # Do not sell in unidirectional chargers
        super()._sell_energy_to_spot_market()
