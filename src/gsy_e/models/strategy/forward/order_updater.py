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

    def __init__(self, parameters: ForwardOrderUpdaterParameters, market_params: MarketSlotParams):
        self._parameters = parameters
        super().__init__(parameters=parameters, market_params=market_params)

    @property
    def capacity_percent(self):
        """Percentage of the total capacity that can be posted by this offer updater."""
        return self._parameters.capacity_percent
