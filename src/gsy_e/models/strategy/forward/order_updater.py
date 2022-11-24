from dataclasses import dataclass

from gsy_e.models.market import MarketSlotParams
from gsy_e.models.strategy.order_updater import OrderUpdater, OrderUpdaterParameters


@dataclass
class ForwardOrderUpdaterParameters(OrderUpdaterParameters):
    """
    Parameters of the order updater class. Includes start / end energy rate and time interval
    between each price update.
    """
    capacity_percent: float

    def __post_init__(self):
        assert 0.0 <= self.capacity_percent <= 100.0


class ForwardOrderUpdater(OrderUpdater):
    """
    Calculate whether the price of the template strategy orders needs to be updated.
    Uses linear increase / decrease in price along the duration of a market slot.
    """
    def __init__(self, parameters: ForwardOrderUpdaterParameters,
                 market_params: MarketSlotParams):
        super().__init__(parameters=parameters, market_params=market_params)

    @property
    def capacity_percent(self):
        """Percentage of the total capacity that can be posted by this offer updater."""
        return self._parameters.capacity_percent
