import sys

from d3a.models.strategy.base import BaseStrategy


class CommercialStrategy(BaseStrategy):
    parameters = ('energy_price')

    def __init__(self, *, energy_price=None):
        if energy_price is not None and energy_price < 0:
            raise ValueError("Energy price should be positive.")
        super().__init__()
        self.energy_price = energy_price
        self.energy = sys.maxsize

    def event_activate(self):
        if self.energy_price is None:
            self.energy_price = self.area.config.market_maker_rate
        # That's usual an init function but the markets aren't open during the init call
        for market in self.area.markets.values():
            market.offer(
                self.energy * self.energy_price,
                self.energy,
                self.owner.name
            )

    def event_trade(self, *, market, trade):
        # If trade happened: remember it in variable
        if self.owner.name == trade.seller:
            market.offer(
                self.energy * self.energy_price,
                self.energy,
                self.owner.name
            )

    def event_market_cycle(self):
        # Post new offers
        market = list(self.area.markets.values())[-1]
        market.offer(
            self.energy * self.energy_price,
            self.energy,
            self.owner.name
        )
