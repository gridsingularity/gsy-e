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

from gsy_e.models.strategy.state.base_states import ProductionState


class PVState(ProductionState):
    """State class for PV devices.

    Completely inherits ProductionState, but we keep this class for backward compatibility.
    """

    def _calculate_unsettled_energy_kWh(
            self, measured_energy_kWh: float, time_slot: DateTime) -> float:
        """
        Returns negative values for overproduction (offer will be placed on the settlement market)
        and positive values for underproduction (bid will be placed on the settlement market)
        :param measured_energy_kWh: Measured energy that the PV produced
        :param time_slot: time slot of the measured energy
        :return: Deviation between forecasted and measured energy
        """
        traded_energy_kWh = (self.get_energy_production_forecast_kWh(time_slot) -
                             self.get_available_energy_kWh(time_slot))
        return traded_energy_kWh - measured_energy_kWh

    def get_results_dict(self, current_time_slot: DateTime) -> dict:
        return {
            "pv_production_kWh": self.get_energy_production_forecast_kWh(current_time_slot),
            "available_energy_kWh": self.get_available_energy_kWh(current_time_slot)
        }
