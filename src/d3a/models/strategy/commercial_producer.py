import random
from typing import Dict  # noqa

from d3a.models.market import Market, Offer  # noqa
from d3a.models.strategy.base import BaseStrategy


class CommercialStrategy(BaseStrategy):
    def __init__(self, *, energy_range_wh=(20, 80), energy_price=30):
        super().__init__()
        self.energy_range_wh = energy_range_wh
        self.energy_price = energy_price
        self.offers_posted = {}  # type: Dict[Offer, Market]

    def event_activate(self):
        # That's usaul an init function but the markets aren't open during the init call
        for market in self.area.markets.values():
            for i in range(20):
                energy = random.randint(*self.energy_range_wh) / 1000
                offer = market.offer(
                    energy,
                    energy * self.energy_price,
                    self.owner.name
                )
                self.offers_posted[offer] = market

    def event_trade(self, *, market, trade):
        # If trade happened: remember it in variable
        if self.owner.name == trade.seller:
            del self.offers_posted[trade.offer]
            energy = random.randint(*self.energy_range_wh) / 1000
            offer = market.offer(
                energy,
                energy * self.energy_price,
                self.owner.name
            )
            self.offers_posted[offer] = market

    def event_market_cycle(self):
        past_market = list(self.area.past_markets.values())[-1]
        for pending_offer, market in list(self.offers_posted.items()):
            if market == past_market:
                del self.offers_posted[pending_offer]
