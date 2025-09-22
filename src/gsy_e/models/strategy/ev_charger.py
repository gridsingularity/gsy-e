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
from typing import Union, Optional

from pendulum import duration, DateTime
from gsy_framework.validators import EVChargerValidator, StorageValidator
from gsy_framework.enums import GridIntegrationType
from gsy_framework.constants_limits import (
    ConstSettings,
    FLOATING_POINT_TOLERANCE,
)
from gsy_framework.utils import get_from_profile_same_weekday_and_time

from gsy_e.models.strategy import BidEnabledStrategy
from gsy_e.gsy_e_core.exceptions import MarketException
from gsy_e.models.strategy.mixins import UseMarketMakerMixin
from gsy_e.models.strategy.state.evcharger_state import EVChargerState, EVChargingSession
from gsy_e.gsy_e_core.util import is_one_sided_market_simulation, is_two_sided_market_simulation
from gsy_e.models.strategy.update_frequency import (
    TemplateStrategyBidUpdater,
    TemplateStrategyOfferUpdater,
)
from gsy_e.models.strategy.storage import StorageStrategy

log = getLogger(__name__)


EVChargerSettings = ConstSettings.EVChargerSettings
StorageSettings = ConstSettings.StorageSettings


class EVChargerStrategy(StorageStrategy):
    """Strategy class EV Charger."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        grid_integration: GridIntegrationType = GridIntegrationType.BIDIRECTIONAL,
        maximum_power_rating_kW: float = EVChargerSettings.MAX_POWER_RATING_KW,
        charging_sessions: list[EVChargingSession] = [],
        initial_selling_rate: Union[float, dict] = StorageSettings.SELLING_RATE_RANGE.initial,
        final_selling_rate: Union[float, dict] = StorageSettings.SELLING_RATE_RANGE.final,
        initial_buying_rate: Union[float, dict] = StorageSettings.BUYING_RATE_RANGE.initial,
        final_buying_rate: Union[float, dict] = StorageSettings.BUYING_RATE_RANGE.final,
        fit_to_limit=True,
        energy_rate_increase_per_update=None,
        energy_rate_decrease_per_update=None,
        update_interval=None,
    ):
        """
        Args:
             grid_integration: connection between the grid and EVs
        """
        EVChargerValidator.validate(
            maximum_power_rating_kW=maximum_power_rating_kW,
            grid_integration=grid_integration,
        )

        super().__init__()

        self.grid_integration = grid_integration
        self.charging_sessions = sorted(charging_sessions, key=lambda s: s.plug_in_time)
        self.active_session_index = None

        if update_interval is None:
            update_interval = duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL
            )
        if isinstance(update_interval, int):
            update_interval = duration(minutes=update_interval)

        self.offer_update = TemplateStrategyOfferUpdater(
            initial_rate=initial_selling_rate,
            final_rate=final_selling_rate,
            fit_to_limit=fit_to_limit,
            energy_rate_change_per_update=energy_rate_decrease_per_update,
            update_interval=update_interval,
        )
        for time_slot in self.offer_update.initial_rate_profile_buffer.keys():
            StorageValidator.validate(
                initial_selling_rate=self.offer_update.initial_rate_profile_buffer[time_slot],
                final_selling_rate=get_from_profile_same_weekday_and_time(
                    self.offer_update.final_rate_profile_buffer, time_slot
                ),
            )
        self.bid_update = TemplateStrategyBidUpdater(
            initial_rate=initial_buying_rate,
            final_rate=final_buying_rate,
            fit_to_limit=fit_to_limit,
            energy_rate_change_per_update=energy_rate_increase_per_update,
            update_interval=update_interval,
            rate_limit_object=min,
        )
        for time_slot in self.bid_update.initial_rate_profile_buffer.keys():
            StorageValidator.validate(
                initial_buying_rate=self.bid_update.initial_rate_profile_buffer[time_slot],
                final_buying_rate=get_from_profile_same_weekday_and_time(
                    self.bid_update.final_rate_profile_buffer, time_slot
                ),
            )

    @property
    def state(self) -> EVChargerState:
        return self._state

    def _maybe_update_session(self, now: DateTime):
        """Switch StorageStrategy state when entering a new session."""
        for idx, charging_session in enumerate(self.charging_sessions):
            start = charging_session.plug_in_time
            end = start.add(minutes=charging_session.duration_minutes)

            if start <= now < end:
                if self.active_session_index != idx:
                    # switch session
                    self.active_session_index = idx
                    self._state = EVChargerState(
                        active_charging_session=charging_session,
                        grid_integration=self.grid_integration,
                    )
                    # reset price updaters and defaults
                    self.offer_update.reset(self)
                    self.bid_update.reset(self)

                    self._update_profiles_with_default_values()

                    self._state.activate(
                        self.simulation_config.slot_length,
                        now,
                    )
                return True
        return False

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
