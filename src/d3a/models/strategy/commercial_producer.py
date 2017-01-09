import random

from d3a.models.strategy.base import BaseStrategy


class Commercial_Strategy(BaseStrategy):
    def __init__(self, *, energy_range=(20, 80),
                 energy_price=30):
        super().__init__()
        self.energy_range = energy_range
        self.energy_price = energy_price
        self.posted_offers = 0

    def event_tick(self, *, area):
        if self.posted_offers < 10:
            energy = random.randint(*self.energy_range) / 100
            time, market = random.choice(list(area.markets.items()))
            offer = market.offer(
                energy,
                energy * self.energy_price,
                self.owner.name
            )
            self.posted_offers += 1
            self.log.info("Offering %s @ %s", offer, time.strftime('%H:%M'))

    def event_trade(self, *, market, trade):
        # If trade happened: remember it in variable
        if self.owner.name == trade.seller:
            self.posted_offers -= 1
