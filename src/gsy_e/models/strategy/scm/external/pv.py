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
from typing import Union, Dict

from gsy_e.models.strategy.scm.external.forecast_mixin import SCMForecastExternalMixin
from gsy_e.models.strategy.scm.pv import SCMPVUserProfile


class ForecastSCMPVStrategy(SCMForecastExternalMixin, SCMPVUserProfile):
    """External SCM PV strategy"""
    # pylint: disable=unused-argument
    def __init__(self, power_profile: Union[str, Dict] = None,
                 power_profile_uuid: str = None):
        """TODO: Remove quickfix of GSYE-581 and remove the unused capacity_kW"""
        super().__init__(power_profile=power_profile, power_profile_uuid=power_profile_uuid)

    def _update_forecast_in_state(self, _area):
        """Overwrite method that sets the forecasted energy in the state."""

    def update_energy_forecast(self) -> None:
        """Set energy forecast for future markets."""
        for slot_time, energy_kWh in self.energy_forecast_buffer.items():
            if slot_time >= self.owner.current_market_time_slot:
                self.state.set_available_energy(energy_kWh, slot_time, overwrite=True)

    def update_energy_measurement(self) -> None:
        """Set energy measurement for past markets."""
        for slot_time, energy_kWh in self.energy_measurement_buffer.items():
            if slot_time < self.owner.current_market_time_slot:
                self.state.set_energy_measurement_kWh(energy_kWh, slot_time)
