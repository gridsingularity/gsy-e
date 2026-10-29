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
from gsy_e.models.strategy.state.storage_state import StorageLosses
from gsy_e.models.strategy.storage import StorageStrategy
from gsy_e.constants import EV_CHARGER_DEFAULT_CHARGING_EFFICIENCY

log = getLogger(__name__)


EVChargerSettings = ConstSettings.EVChargerSettings
StorageSettings = ConstSettings.StorageSettings


class EVChargerStrategy(StorageStrategy):
    """Strategy class EV Charger. Similar to StorageStrategy but only during active sessions."""

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        grid_integration: GridIntegrationType = GridIntegrationType.UNIDIRECTIONAL,
        charging_sessions: list[EVChargingSession] = None,
        maximum_power_rating_kW: float = ConstSettings.EVChargerSettings.MAX_POWER_RATING_KW,
        preferred_charging_power: Optional[Union[float, Dict[DateTime, float]]] = None,
        charging_efficiency: float = EV_CHARGER_DEFAULT_CHARGING_EFFICIENCY,
        **kwargs,
    ):
        """
        Args:
             grid_integration: connection between the grid and EVs
             preferred_charging_power: User-specified charging power (kW) per market slot that
                replaces default strategy. Can be a constant value or time-based profile.
             charging_efficiency: Efficiency of charging/discharging (default 0.9 = 90%)
        """
        if not charging_sessions:
            charging_sessions = []
        EVChargerValidator.validate(
            grid_integration=grid_integration,
            maximum_power_rating_kW=maximum_power_rating_kW,
            preferred_charging_power=preferred_charging_power,
        )

        # Convert efficiency to loss percentage for both charging and discharging
        loss_percent = 1.0 - charging_efficiency
        losses = kwargs.get("losses")
        if not losses:
            losses = StorageLosses(
                charging_loss_percent=loss_percent,
                discharging_loss_percent=loss_percent,
            )
            kwargs["losses"] = losses

        super().__init__(**kwargs)

        self.grid_integration = grid_integration
        self.maximum_power_rating_kW = maximum_power_rating_kW
        self.preferred_charging_power = preferred_charging_power
        self.charging_sessions = sorted(charging_sessions, key=lambda s: s.plug_in_time)
        self.status = EVChargerStatus.IDLE

        # Convert preferred_charging_power to profile if provided
        preferred_power_profile = None
        if preferred_charging_power is not None:
            preferred_power_profile = UserProfileReader().read_arbitrary_profile(
                InputProfileTypes.IDENTITY, preferred_charging_power
            )

        self._state = EVChargerState(
            maximum_power_rating_kW=self.maximum_power_rating_kW,
            charging_sessions=self.charging_sessions,
            preferred_power_profile=preferred_power_profile,
            slot_length=GlobalConfig.slot_length,
            losses=losses,
        )

    @property
    def state(self) -> EVChargerState:
        return self._state

    def _update_session_state(self) -> None:
        """Update charging session state based on current time slot."""
        now = self.area.spot_market.time_slot

        has_active = self._state.ev_sessions_manager.has_active_sessions(now)
        if has_active and self.status == EVChargerStatus.IDLE:
            # activate charger when at least one session becomes active
            self._update_profiles_with_default_values()
            self._state.activate(self.simulation_config.slot_length, now)
            self._state.add_default_values_to_state_profiles([now])
            self.status = EVChargerStatus.ACTIVE
        elif not has_active and self.status == EVChargerStatus.ACTIVE:
            # deactivate charger when no sessions are active
            self.status = EVChargerStatus.IDLE

    def event_activate(self, **kwargs):
        self._update_session_state()
        if self.status == EVChargerStatus.IDLE:
            return  # skip if no charging session is active
        super().event_activate(**kwargs)

    def event_market_cycle(self):
        self._update_session_state()
        if self.status == EVChargerStatus.IDLE:
            return  # skip if no charging session is active
        super().event_market_cycle()

    def event_tick(self):
        self._update_session_state()
        if self.status == EVChargerStatus.IDLE:
            return  # skip if no charging session is active
        super().event_tick()

    def _sell_energy_to_spot_market(self):
        if self.grid_integration == GridIntegrationType.UNIDIRECTIONAL:
            return  # Do not sell in unidirectional chargers
        super()._sell_energy_to_spot_market()

    def event_offer_traded(self, *, market_id, trade):
        """Handle offer trades (selling energy from EVs)."""
        super().event_offer_traded(market_id=market_id, trade=trade)

        if trade.seller.name == self.owner.name:
            self._state.ev_sessions_manager.distribute_sold_energy(
                trade.time_slot, trade.traded_energy
            )

    def event_bid_traded(self, *, market_id, bid_trade):
        """Handle bid trades (buying energy for EVs)."""
        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)

        if bid_trade.buyer.name == self.owner.name:
            self._state.ev_sessions_manager.distribute_bought_energy(
                bid_trade.time_slot, bid_trade.traded_energy
            )
