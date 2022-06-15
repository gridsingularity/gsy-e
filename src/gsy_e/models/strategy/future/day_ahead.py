"""
Copyright 2018 Grid Singularity
This file is part of D3A.

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
from typing import TYPE_CHECKING, Optional

from gsy_framework.constants_limits import ConstSettings
from pendulum import DateTime

from gsy_e.constants import DayAheadTemplateStrategiesConstants
from gsy_e.models.strategy.future.strategy import FutureMarketStrategyInterface

if TYPE_CHECKING:
    from gsy_e.models.strategy import BaseStrategy


class DayAheadMarketStrategy(FutureMarketStrategyInterface):
    """Template strategy for day-ahead markets"""

    def __init__(self, initial_buying_rate: Optional[float], final_buying_rate: Optional[float],
                 initial_selling_rate: Optional[float], final_selling_rate: Optional[float]):

        super().__init__()

        self.initial_buying_rate = initial_buying_rate
        self.final_buying_rate = final_buying_rate
        self.initial_selling_rate = initial_selling_rate
        self.final_selling_rate = final_selling_rate

    def event_market_cycle(self, strategy: "BaseStrategy") -> None:
        self._post_first_offers_on_markets(strategy.area.day_ahead_markets, strategy)

    def _post_consumer_first_bid(
            self, strategy: "BaseStrategy", time_slot: DateTime, available_buy_energy_kWh: float
    ) -> None:

        if available_buy_energy_kWh <= 0.0:
            return
        if strategy.get_posted_bids(strategy.area.day_ahead_markets, time_slot):
            return
        selling_rate = abs(self.initial_selling_rate - self.final_selling_rate) / 2
        strategy.post_bid(
            market=strategy.area.day_ahead_markets,
            energy=available_buy_energy_kWh,
            price=available_buy_energy_kWh * selling_rate,
            time_slot=time_slot,
            replace_existing=False
        )

    def _post_producer_first_offer(
            self, strategy: "BaseStrategy", time_slot: DateTime, available_sell_energy_kWh: float
    ) -> None:
        if available_sell_energy_kWh <= 0.0:
            return
        if strategy.get_posted_offers(strategy.area.day_ahead_markets, time_slot):
            return
        buying_rate = abs(self.final_buying_rate - self.initial_buying_rate) / 2
        strategy.post_offer(
            market=strategy.area.day_ahead_markets,
            energy=available_sell_energy_kWh,
            price=available_sell_energy_kWh * buying_rate,
            time_slot=time_slot,
            replace_existing=False
        )


def day_ahead_strategy_factory(
        initial_buying_rate: float = DayAheadTemplateStrategiesConstants.INITIAL_BUYING_RATE,
        final_buying_rate: float = DayAheadTemplateStrategiesConstants.FINAL_BUYING_RATE,
        initial_selling_rate: float = DayAheadTemplateStrategiesConstants.INITIAL_SELLING_RATE,
        final_selling_rate: float = DayAheadTemplateStrategiesConstants.FINAL_SELLING_RATE
) -> FutureMarketStrategyInterface:
    """Create day-ahead market template strategy if day-ahead markets are enabled."""

    if ConstSettings.FutureMarketSettings.DAY_AHEAD_DURATION_DAYS > 0:
        return DayAheadMarketStrategy(
            initial_buying_rate, final_buying_rate,
            initial_selling_rate, final_selling_rate)
    return FutureMarketStrategyInterface(
        None, initial_buying_rate, final_buying_rate,
        initial_selling_rate, final_selling_rate
    )
