from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pendulum import DateTime

if TYPE_CHECKING:
    from gsy_e.models.area import Area


class SCMStrategy(ABC):
    """Abstract base class for all SCM strategies."""

    @abstractmethod
    def activate(self, area: "Area"):
        """Trigger strategy actions at the start of the simulation, when the area is activated."""
        raise NotImplementedError

    @abstractmethod
    def market_cycle(self, area: "Area"):
        """Trigger strategy actions on every market cycle."""
        raise NotImplementedError

    # pylint: disable=unused-argument,no-self-use
    def get_energy_to_sell_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for production for the specified time slot."""
        return 0.

    def get_energy_to_buy_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for consumption for the specified time slot."""
        return 0.
