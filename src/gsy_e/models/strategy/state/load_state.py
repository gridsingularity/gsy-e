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

from pendulum import DateTime

from gsy_e.models.strategy.state.base_states import ConsumptionState


class LoadState(ConsumptionState):
    """State for the load asset."""

    @property
    def total_energy_demanded_Wh(self) -> float:
        """Return the total energy demanded in Wh."""
        return self._total_energy_demanded_Wh

    def _calculate_unsettled_energy_kWh(
            self, measured_energy_kWh: float, time_slot: DateTime) -> float:
        """
        Returns negative values for underconsumption (offer will be placed on the settlement
        market) and positive values for overconsumption (bid will be placed on the settlement
        market)
        :param measured_energy_kWh: Measured energy that the load produced
        :param time_slot: time slot of the measured energy
        :return: Deviation between forecasted and measured energy
        """
        traded_energy_kWh = (self.get_desired_energy_Wh(time_slot) -
                             self.get_energy_requirement_Wh(time_slot)) / 1000.0
        return measured_energy_kWh - traded_energy_kWh

    def get_results_dict(self, current_time_slot: DateTime) -> dict:
        return {
            "load_profile_kWh": self.get_desired_energy_Wh(current_time_slot) / 1000.0,
            "total_energy_demanded_wh": self.total_energy_demanded_Wh,
            "energy_requirement_kWh": self.get_energy_requirement_Wh(current_time_slot) / 1000.0
        }
