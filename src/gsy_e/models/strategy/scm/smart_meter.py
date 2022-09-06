from pathlib import Path
from typing import Union, Dict, TYPE_CHECKING

from pendulum import DateTime

from gsy_e.models.strategy.scm import SCMStrategy
from gsy_e.models.strategy.energy_parameters.smart_meter import SmartMeterEnergyParameters

if TYPE_CHECKING:
    from gsy_e.models.area import CoefficientArea
    from gsy_e.models.state import SmartMeterState


class SCMSmartMeterStrategy(SCMStrategy):
    """Storage SCM strategy."""
    # pylint: disable=too-many-arguments
    def __init__(
            self, smart_meter_profile: Union[Path, str, Dict[int, float], Dict[str, float]] = None,
            smart_meter_profile_uuid: str = None):
        self._energy_params = SmartMeterEnergyParameters(
            smart_meter_profile, smart_meter_profile_uuid)

    @property
    def state(self) -> "SmartMeterState":
        """Fetch the state of the smart meter."""
        return self._energy_params._state  # pylint: disable=protected-access

    def serialize(self):
        """Create dict with smart meter SCM energy parameters."""
        return self._energy_params.serialize()

    def activate(self, area: "CoefficientArea") -> None:
        """Activate the strategy."""
        self._energy_params.activate(area)
        self._energy_params.set_energy_forecast_for_future_markets(
            [area._current_market_time_slot], reconfigure=True)

    def market_cycle(self, area: "CoefficientArea") -> None:
        """Update the storage state for the next time slot."""
        self._energy_params.set_energy_forecast_for_future_markets(
            [area._current_market_time_slot], reconfigure=False)
        self._energy_params.set_energy_measurement_kWh(area._current_market_time_slot)
        self.state.delete_past_state_values(area.past_market_time_slot)

    def get_energy_to_sell_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for production for the specified time slot."""
        return self.state.get_available_energy_kWh(time_slot)

    def get_energy_to_buy_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for consumption for the specified time slot."""
        return self.state.get_energy_requirement_Wh(time_slot) / 1000.0

    def decrease_energy_to_sell(
            self, traded_energy_kWh: float, time_slot: DateTime, area: "CoefficientArea"):
        """Decrease traded energy from the state and the strategy parameters."""
        self._energy_params.decrement_energy_requirement(
            energy_kWh=traded_energy_kWh,
            time_slot=time_slot,
            area_name=area.name)

    def decrease_energy_to_buy(
            self, traded_energy_kWh: float, time_slot: DateTime, area: "CoefficientArea"):
        """Decrease traded energy from the state and the strategy parameters."""
        self.state.decrement_available_energy(traded_energy_kWh, time_slot, area.name)
