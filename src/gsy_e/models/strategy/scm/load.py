from typing import Dict, TYPE_CHECKING

from pendulum import DateTime
from gsy_framework.constants_limits import GlobalConfig

from gsy_e.models.strategy.energy_parameters.load import (
    LoadHoursEnergyParameters, DefinedLoadEnergyParameters)
from gsy_e.models.strategy.scm import SCMStrategy

if TYPE_CHECKING:
    from gsy_e.models.area import AreaBase


class SCMLoadHoursStrategy(SCMStrategy):
    """Load SCM strategy with constant power production."""
    def __init__(self, avg_power_W, hrs_of_day=None):
        self._energy_params = LoadHoursEnergyParameters(avg_power_W, hrs_of_day)
        self._simulation_start_timestamp = None

    @property
    def state(self):
        """Return the state of energy parameters."""
        return self._energy_params.state

    def activate(self, area: "AreaBase") -> None:
        """Activate the strategy."""
        self._energy_params.event_activate_energy(area)
        self._update_energy_requirement_and_measurement(area)
        self._simulation_start_timestamp = area.now

    def _get_day_of_timestamp(self, time_slot: DateTime) -> int:
        """Return the number of days passed from the simulation start date to the time slot."""
        if self._simulation_start_timestamp is None:
            return 0
        return (time_slot - self._simulation_start_timestamp).days

    def market_cycle(self, area: "AreaBase") -> None:
        """Update the load forecast and measurements for the next/previous market slot."""
        self._update_energy_requirement_and_measurement(area)

    def _update_energy_requirement_and_measurement(self, area: "AreaBase"):
        self._energy_params.update_energy_requirement(area.current_market_time_slot)

        if not self._energy_params.allowed_operating_hours(area.current_market_time_slot):
            # Overwrite desired energy to 0 in case the previous step has populated the
            # desired energy by the hrs_per_day have been exhausted.
            self._energy_params.state.set_desired_energy(0.0, area.current_market_time_slot, True)
        if area.current_market_time_slot:
            self._energy_params.state.update_total_demanded_energy(area.current_market_time_slot)
        self._energy_params.set_energy_measurement_kWh(area.past_market_time_slot)

    def get_energy_to_buy_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for consumption for the specified time slot."""
        return self._energy_params.state.get_energy_requirement_Wh(time_slot) / 1000.0

    def serialize(self):
        return {**self._energy_params.serialize()}


class SCMLoadProfileStrategy(SCMStrategy):
    """Load SCM strategy with power consumption dictated by a profile."""
    def __init__(self, daily_load_profile=None,
                 daily_load_profile_uuid: str = None):
        self._energy_params = DefinedLoadEnergyParameters(
            daily_load_profile, daily_load_profile_uuid)

        # needed for profile_handler
        self.daily_load_profile_uuid = daily_load_profile_uuid

    @property
    def state(self):
        """Return state of energy parameters."""
        return self._energy_params.state

    def serialize(self) -> Dict:
        """Serialize the strategy parameters."""
        return self._energy_params.serialize()

    def activate(self, area: "AreaBase") -> None:
        """Activate the strategy."""
        self._energy_params.event_activate_energy(area)

    def _update_energy_requirement(self, area: "AreaBase") -> None:
        self._energy_params.energy_profile.read_or_rotate_profiles()
        self._energy_params.update_energy_requirement(area.current_market_time_slot)
        self._energy_params.set_energy_measurement_kWh(area.past_market_time_slot)

    def market_cycle(self, area: "AreaBase") -> None:
        """Update the load forecast and measurements for the next/previous market slot."""
        self._update_energy_requirement(area)

    def get_available_energy_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for consumption for the specified time slot."""
        return self._energy_params.state.get_energy_requirement_Wh(time_slot) / 1000.0

    def get_energy_to_buy_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for consumption for the specified time slot."""
        return self._energy_params.state.get_energy_requirement_Wh(time_slot) / 1000.0

    @staticmethod
    def deserialize_args(constructor_args: Dict) -> Dict:
        if not GlobalConfig.is_canary_network():
            return constructor_args
        # move measurement_uuid into forecast uuid because this is only used in SCM
        measurement_uuid = constructor_args.get("daily_load_measurement_uuid")
        if measurement_uuid:
            constructor_args["daily_load_profile_uuid"] = measurement_uuid
        return constructor_args
