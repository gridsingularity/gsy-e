from abc import ABC, abstractmethod


class SCMStrategy(ABC):
    """Abstract base class for all SCM strategies."""

    @abstractmethod
    def activate(self, area):
        """Trigger strategy actions at the start of the simulation, when the area is activated."""
        raise NotImplementedError

    @abstractmethod
    def market_cycle(self, area):
        """Trigger strategy actions on every market cycle."""
        raise NotImplementedError
