from typing import Union, Dict

from gsy_e.models.strategy.predefined_pv import (
    PVPredefinedEnergyParameters, PVUserProfileEnergyParameters)
from gsy_e.models.strategy.pv import PVEnergyParameters
from gsy_e.models.strategy.scm import SCMStrategy


class SCMPVStrategy(SCMStrategy):
    """PV SCM strategy with gaussian power production."""

    def __init__(self, panel_count: int = 1, capacity_kW: float = None):
        if not hasattr(self, "_energy_params"):
            self._energy_params = PVEnergyParameters(panel_count, capacity_kW)

    @property
    def _state(self):
        # pylint: disable=protected-access
        return self._energy_params._state

    def activate(self, area):
        """Activate the strategy."""
        self._energy_params.activate(area.simulation_config)
        self._energy_params.set_produced_energy_forecast(
            area.current_market.time_slot, area.simulation_config.slot_length)

    def market_cycle(self, area):
        """Update the load forecast and measurements for the next/previous market slot."""
        self._energy_params.set_energy_measurement_kWh(area.past_market.time_slot)
        self._energy_params.set_produced_energy_forecast(
            area.current_market.time_slot, area.simulation_config.slot_length)
        self._state.delete_past_state_values(area.past_market.time_slot)

    def get_available_energy_kWh(self, time_slot):
        """Get the available energy for production for the specified time slot."""
        return self._state.get_available_energy_kWh(time_slot)


class SCMPVPredefinedStrategy(SCMPVStrategy):
    """PV SCM strategy with predefined profile production."""
    def __init__(self, panel_count: int = 1, cloud_coverage: int = None,
                 capacity_kW: float = None):
        self._energy_params = PVPredefinedEnergyParameters(
            panel_count, cloud_coverage, capacity_kW)
        super().__init__(panel_count, capacity_kW)


class SCMPVUserProfile(SCMPVStrategy):
    """PV SCM strategy with user uploaded profile production."""
    def __init__(self, panel_count: int = 1, power_profile: Union[str, Dict] = None,
                 power_profile_uuid: str = None):
        self._energy_params = PVUserProfileEnergyParameters(
            panel_count, power_profile, power_profile_uuid)
        super().__init__(panel_count)
