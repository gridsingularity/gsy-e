from typing import Union, Dict, TYPE_CHECKING

from pendulum import DateTime

from gsy_e.models.strategy.predefined_pv import (
    PVPredefinedEnergyParameters, PVUserProfileEnergyParameters)
from gsy_e.models.strategy.pv import PVEnergyParameters
from gsy_e.models.strategy.scm import SCMStrategy

if TYPE_CHECKING:
    from gsy_e.models.area import AreaBase
    from gsy_e.models.state import StateInterface


class SCMPVStrategy(SCMStrategy):
    """PV SCM strategy with gaussian power production."""

    def __init__(self, capacity_kW: float = None):
        if not hasattr(self, "_energy_params"):
            self._energy_params = PVEnergyParameters(1, capacity_kW)

    def serialize(self) -> Dict:
        """Serialize the strategy parameters."""
        return self._energy_params.serialize()

    @property
    def _state(self) -> "StateInterface":
        # pylint: disable=protected-access
        return self._energy_params._state

    def activate(self, area: "AreaBase") -> None:
        """Activate the strategy."""
        self._energy_params.activate(area.simulation_config)
        self._energy_params.set_produced_energy_forecast(
            area.current_market_time_slot, area.simulation_config.slot_length)

    def market_cycle(self, area: "AreaBase") -> None:
        """Update the load forecast and measurements for the next/previous market slot."""
        self._energy_params.set_energy_measurement_kWh(area.past_market_time_slot)
        self._energy_params.set_produced_energy_forecast(
            area.current_market_time_slot, area.simulation_config.slot_length)
        self._state.delete_past_state_values(area.past_market_time_slot)

    def get_available_energy_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for production for the specified time slot."""
        return self._state.get_available_energy_kWh(time_slot)


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
