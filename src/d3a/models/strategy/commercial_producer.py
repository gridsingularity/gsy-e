import random
from typing import Dict  # noqa

from d3a.models.market import Market, Offer  # noqa
from d3a.models.strategy.base import BaseStrategy


class CommercialStrategy(BaseStrategy):
    def __init__(self, *, energy_range_wh=(40, 160), energy_price=30):
        super().__init__()
        self.energy_range_wh = energy_range_wh
        self.energy_price = energy_price
        self.offers_posted = {}  # type: Dict[Offer, Market]

    def event_tick(self, *, area):
        if len(self.offers_posted) < 10 * self.owner.config.market_count:
            energy = random.randint(*self.energy_range_wh) / 1000
            time, market = random.choice(list(area.markets.items()))
            offer = market.offer(
                energy,
                energy * self.energy_price,
                self.owner.name
            )
            self.offers_posted[offer] = market
            self.log.info("Offering %s @ %s", offer, time.strftime('%H:%M'))

        try:
            next_market = list(self.area.markets.values())[0]
            if next_market not in self.offers_posted.values():
                energy = random.randint(*self.energy_range_wh) / 1000
                offer = next_market.offer(
                            energy,
                            energy * self.energy_price,
                            self.owner.name
                        )
                self.offers_posted[offer] = self.area.current_market
        except Exception:
            self.log.critical("no markets open?!")

    def event_trade(self, *, market, trade):
        # If trade happened: remember it in variable
        if self.owner.name == trade.seller:
            del self.offers_posted[trade.offer]

    def event_market_cycle(self):
        past_market = list(self.area.past_markets.values())[-1]
        for pending_offer, market in list(self.offers_posted.items()):
            if market == past_market:
                del self.offers_posted[pending_offer]
