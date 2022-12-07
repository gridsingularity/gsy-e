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

from gsy_e.models.strategy.external_strategies.forecast_mixin import ForecastExternalMixin
from gsy_e.constants import DATE_TIME_FORMAT

if TYPE_CHECKING:
    from gsy_e.models.area.coefficient_area import CoefficientArea


class SCMForecastExternalMixin(ForecastExternalMixin):
    """External mixin for forecast strategies in SCM simulations."""

    def activate(self, area: "CoefficientArea") -> None:
        """Activate the device."""
        super().activate(area)
        self.redis.sub_to_multiple_channels(self.channel_dict)

    @property
    def channel_dict(self) -> Dict:
        """Common API interfaces for all external assets/markets."""
        return {
            f"{self.channel_prefix}/register_participant": self._register,
            f"{self.channel_prefix}/unregister_participant": self._unregister,
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
        self.update_energy_forecast()
        self.update_energy_measurement()
        self._clear_energy_buffers()
