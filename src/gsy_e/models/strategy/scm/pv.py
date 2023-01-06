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

from typing import Union, Dict, TYPE_CHECKING

from pendulum import DateTime

from gsy_e.models.strategy.energy_parameters.pv import (
    PVEnergyParameters, PVPredefinedEnergyParameters, PVUserProfileEnergyParameters)
from gsy_e.models.strategy.scm import SCMStrategy

if TYPE_CHECKING:
    from gsy_e.models.area import AreaBase, CoefficientArea
    from gsy_e.models.strategy.state import StateInterface


class SCMPVStrategy(SCMStrategy):
    """PV SCM strategy with gaussian power production."""

    def __init__(self, capacity_kW: float = None):
        if not hasattr(self, "_energy_params"):
            self._energy_params = PVEnergyParameters(1, capacity_kW)

    def serialize(self) -> Dict:
        """Serialize the strategy parameters."""
        return self._energy_params.serialize()

    @property
    def state(self) -> "StateInterface":
        # pylint: disable=protected-access
        return self._energy_params._state

    def activate(self, area: "AreaBase") -> None:
        """Activate the strategy."""
        self._energy_params.activate(area.config)
        self._energy_params.set_produced_energy_forecast(
            area.current_market_time_slot, area.config.slot_length)

    def market_cycle(self, area: "AreaBase") -> None:
        """Update the PV forecast and measurements for the next/previous market slot."""
        self._energy_params.set_energy_measurement_kWh(area.past_market_time_slot)
        self._energy_params.set_produced_energy_forecast(
            area.current_market_time_slot, area.config.slot_length)
        self.state.delete_past_state_values(area.past_market_time_slot)

    def get_energy_to_sell_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for production for the specified time slot."""
        return self.state.get_available_energy_kWh(time_slot)

    def decrease_energy_to_sell(
            self, traded_energy_kWh: float, time_slot: DateTime, area: "CoefficientArea"):
        """Decrease traded energy from the state and the strategy parameters."""
        self.state.decrement_available_energy(traded_energy_kWh, time_slot, area.name)


class SCMPVPredefinedStrategy(SCMPVStrategy):
    """PV SCM strategy with predefined profile production."""
    def __init__(self, cloud_coverage: int = None, capacity_kW: float = None):
        self._energy_params = PVPredefinedEnergyParameters(1, cloud_coverage, capacity_kW)
        super().__init__(capacity_kW)


class SCMPVUserProfile(SCMPVStrategy):
    """PV SCM strategy with user uploaded profile production."""
    def __init__(self, power_profile: Union[str, Dict] = None,
                 power_profile_uuid: str = None):
        self._energy_params = PVUserProfileEnergyParameters(1, power_profile, power_profile_uuid)
        super().__init__()
        self.power_profile_uuid = power_profile_uuid

    def _update_forecast_in_state(self, area):
        self._energy_params.read_predefined_profile_for_pv()
        self._energy_params.set_produced_energy_forecast_in_state(
            area.name, [area.current_market_time_slot], True
        )

    def activate(self, area: "AreaBase") -> None:
        self._energy_params.activate(area.config)
        self._update_forecast_in_state(area)

    def market_cycle(self, area: "AreaBase") -> None:
        self._update_forecast_in_state(area)
        self.state.delete_past_state_values(area.past_market_time_slot)
