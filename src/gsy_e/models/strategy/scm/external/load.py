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
from gsy_e.models.strategy.scm.external.forecast_mixin import SCMForecastExternalMixin
from gsy_e.models.strategy.scm.load import SCMLoadProfileStrategy


class ForecastSCMLoadStrategy(SCMForecastExternalMixin, SCMLoadProfileStrategy):
    """External SCM Load strategy"""

    # def _update_energy_requirement(self, _area):
    #     """Overwrite method that sets the energy requirement in the state."""

    def update_energy_forecast(self) -> None:
        """Set energy forecast for future markets."""
        for slot_time, energy_kWh in self.energy_forecast_buffer.items():
            if slot_time >= self.owner.current_market_time_slot:
                self.state.set_desired_energy(energy_kWh * 1000, slot_time, overwrite=True)
                self.state.update_total_demanded_energy(slot_time)

    def update_energy_measurement(self) -> None:
        """Set energy measurement for past markets."""
        for slot_time, energy_kWh in self.energy_measurement_buffer.items():
            if slot_time < self.owner.current_market_time_slot:
                self.state.set_energy_measurement_kWh(energy_kWh, slot_time)
