import sys
from d3a.models.strategy import ureg, Q_

from d3a.models.strategy.base import BaseStrategy


class CommercialStrategy(BaseStrategy):

    def __init__(self, energy_rate=None):
        if energy_rate is not None and energy_rate < 0:
            raise ValueError("Energy price should be positive.")
        super().__init__()
        self.energy = Q_(int(sys.maxsize), ureg.kWh)

    def event_activate(self):
        # That's usually an init function but the markets aren't open during the init call
        for market in self.area.markets.values():
            market.offer(
                self.energy.m * self.area.config.market_maker_rate[market.time_slot.hour],
                self.energy.m,
                self.owner.name
            )

    def event_trade(self, *, market, trade):
        # If trade happened: remember it in variable
        if self.owner.name == trade.seller:
            market.offer(
                self.energy.m * self.area.config.market_maker_rate[market.time_slot.hour],
                self.energy.m,
                self.owner.name
            )

    def event_market_cycle(self):
        # Post new offers
        market = list(self.area.markets.values())[-1]
        market.offer(
            self.energy.m * self.area.config.market_maker_rate[market.time_slot.hour],
            self.energy.m,
            self.owner.name
        )
