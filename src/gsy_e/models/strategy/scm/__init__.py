from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict

from gsy_framework.exceptions import GSyException

from pendulum import DateTime

if TYPE_CHECKING:
    from gsy_e.models.area import CoefficientArea


class SCMStrategy(ABC):
    """Abstract base class for all SCM strategies."""

    @property
    @abstractmethod
    def state(self):
        """Return state of the strategy."""

    @abstractmethod
    def activate(self, area: "CoefficientArea"):
        """Trigger strategy actions at the start of the simulation, when the area is activated."""
        raise NotImplementedError

    @abstractmethod
    def market_cycle(self, area: "CoefficientArea"):
        """Trigger strategy actions on every market cycle."""
        raise NotImplementedError

    @abstractmethod
    def serialize(self):
        """Serialize SCMStrategy object"""
        raise NotImplementedError

    def get_state(self) -> Dict:
        """Retrieve the current state object of the strategy in dict format."""
        try:
            return self.state.get_state()
        except AttributeError as ex:
            raise GSyException(
                "Strategy does not have a state. "
                "State is required to support save state functionality.") from ex

    def restore_state(self, saved_state: Dict) -> None:
        """Restore the current state object of the strategy from dict format."""
        try:
            self.state.restore_state(saved_state)
        except AttributeError as ex:
            raise GSyException(
                "Strategy does not have a state. "
                "State is required to support load state functionality.") from ex

    # pylint: disable=unused-argument,no-self-use
    def get_energy_to_sell_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for production for the specified time slot."""
        return 0.

    def get_energy_to_buy_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for consumption for the specified time slot."""
        return 0.

    def deactivate(self):
        """Should be called when the simulation is ended."""

    def area_reconfigure_event(self, **kwargs):
        """Needed for live events."""

    def activate_energy_parameters(self, current_time_slot: DateTime) -> None:
        """Needed for live events."""

    @staticmethod
    def deserialize_args(constructor_args: Dict) -> Dict:
        """Deserialize the constructor arguments."""
        return constructor_args
