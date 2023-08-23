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

from typing import Dict, TYPE_CHECKING

from gsy_framework.redis_channels import ExternalStrategyChannels

import gsy_e
from gsy_e.constants import DATE_TIME_FORMAT
from gsy_e.models.strategy.external_strategies.forecast_mixin import ForecastExternalMixin

if TYPE_CHECKING:
    from gsy_e.models.area import CoefficientArea


class SCMForecastExternalMixin(ForecastExternalMixin):
    """External mixin for forecast strategies in SCM simulations."""

    def activate(self, _area: "CoefficientArea") -> None:
        """Overwrite in order to not trigger the profile rotation."""
        self.channel_names = ExternalStrategyChannels(
            gsy_e.constants.EXTERNAL_CONNECTION_WEB,
            gsy_e.constants.CONFIGURATION_ID,
            asset_uuid=self.device.uuid,
            asset_name=self.device.name
        )
        self.sub_to_redis_channels()

    def sub_to_redis_channels(self):
        """Subscribe to redis channels for (un-)registering."""
        self.redis.sub_to_multiple_channels(self.channel_dict)

    @property
    def channel_dict(self) -> Dict:
        """Common API interfaces for all external assets/markets."""
        return {
            self.channel_names.register: self._register,
            self.channel_names.unregister: self._unregister,
        }

    @property
    def _aggregator_command_callback_mapping(self) -> Dict:
        """Only subscribe to channels that are needed for scm external strategies."""
        return {
            "set_energy_forecast": self._set_energy_forecast_aggregator,
            "set_energy_measurement": self._set_energy_measurement_aggregator
        }

    @property
    def _progress_info(self) -> Dict:
        """Return the progress information of the simulation."""
        return {"market_slot": self.owner.current_market_time_slot.format(DATE_TIME_FORMAT)}

    def market_cycle(self, _area) -> None:
        """Call forecast and measurement update."""
        super().market_cycle(_area)
        self.update_energy_forecast()
        self.update_energy_measurement()
        self._clear_energy_buffers()
