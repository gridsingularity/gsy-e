import random

from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import COMMERCIAL_OFFERS


class CommercialStrategy(BaseStrategy):
    def __init__(self, *, energy_range_wh=(20, 80), energy_price=30):
        super().__init__()
        self.energy_range_wh = energy_range_wh
        self.energy_price = energy_price

    def event_activate(self):
        # That's usaul an init function but the markets aren't open during the init call
        for market in self.area.markets.values():
            for i in range(COMMERCIAL_OFFERS):
                energy = random.randint(*self.energy_range_wh) / 1000
                market.offer(
                    energy * self.energy_price,
                    energy,
                    self.owner.name
                )

    def event_trade(self, *, market, trade):
        # If trade happened: remember it in variable
        if self.owner.name == trade.seller:
            energy = random.randint(*self.energy_range_wh) / 1000
            market.offer(
                energy * self.energy_price,
                energy,
                self.owner.name
            )

    def event_market_cycle(self):
        # Post new offers
        market = list(self.area.markets.values())[-1]
        for i in range(COMMERCIAL_OFFERS):
            energy = random.randint(*self.energy_range_wh) / 1000
            market.offer(
                energy * self.energy_price,
                energy,
                self.owner.name
            )
