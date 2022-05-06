from typing import Dict, TYPE_CHECKING

from pendulum import DateTime

from gsy_e.models.strategy.load_hours import LoadHoursEnergyParameters
from gsy_e.models.strategy.predefined_load import DefinedLoadEnergyParameters
from gsy_e.models.strategy.scm import SCMStrategy

if TYPE_CHECKING:
    from gsy_e.models.area import AreaBase


class SCMLoadHoursStrategy(SCMStrategy):
    """Load SCM strategy with constant power production."""
    def __init__(self, avg_power_W, hrs_per_day=None, hrs_of_day=None):
        self._energy_params = LoadHoursEnergyParameters(
            avg_power_W, hrs_per_day, hrs_of_day)
        self._simulation_start_timestamp = None

    def activate(self, area: "AreaBase") -> None:
        """Activate the strategy."""
        self._energy_params.event_activate_energy(area)
        self._simulation_start_timestamp = area.now

    def _get_day_of_timestamp(self, time_slot: DateTime) -> int:
        """Return the number of days passed from the simulation start date to the time slot."""
        if self._simulation_start_timestamp is None:
            return 0
        return (time_slot - self._simulation_start_timestamp).days

    def market_cycle(self, area: "AreaBase") -> None:
        """Update the load forecast and measurements for the next/previous market slot."""
        self._energy_params.add_entry_in_hrs_per_day(
            self._get_day_of_timestamp(area.current_time_slot)
        )
        # self._update_energy_requirement_in_state()
        # # Provide energy values for the past market slot, to be used in the settlement market
        # self._set_energy_measurement_of_last_market()

    def get_available_energy_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for consumption for the specified time slot."""
        return self._energy_params.state.get_energy_requirement_Wh(time_slot) / 1000.0


class SCMLoadProfile(SCMStrategy):
    """Load SCM strategy with power production dictated by a profile."""
    def __init__(self, daily_load_profile, daily_load_profile_uuid=None):
        self._energy_params = DefinedLoadEnergyParameters(
            daily_load_profile, daily_load_profile_uuid)

    def serialize(self) -> Dict:
        """Serialize the strategy parameters."""
        return self._energy_params.serialize()

    def activate(self, area: "AreaBase") -> None:
        """Activate the strategy."""
        self._energy_params.event_activate_energy()

    def market_cycle(self, area: "AreaBase") -> None:
        """Update the load forecast and measurements for the next/previous market slot."""
        self._energy_params.read_or_rotate_profiles()
        slot_time = area.current_market_time_slot
        self._energy_params.update_energy_requirement(slot_time, area.name)

    def get_available_energy_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for consumption for the specified time slot."""
        return self._energy_params.state.get_energy_requirement_Wh(time_slot) / 1000.0
