import random

from d3a.exceptions import MarketException
from d3a.models.strategy.base import BaseStrategy


class BuyStrategy(BaseStrategy):
    def __init__(self, *, buy_chance=0.1):
        super().__init__()
        self.buy_chance = buy_chance

    def event_tick(self, *, area):
        if random.random() <= self.buy_chance:
            time, market = random.choice(list(area.markets.items()))
            for offer in market.sorted_offers:
                try:
                    market.accept_offer(offer, self.owner.name)
                    self.log.info("Buying %s", offer)
                    break
                except MarketException:
                    # Offer already gone etc., use next one.
                    continue
        # Report consumption


class OfferStrategy(BaseStrategy):
    def __init__(self, *, offer_chance=0.01, energy_range=(2, 10), price_fraction_choice=(3, 4)):
        super().__init__()
        self.offer_chance = offer_chance
        self.energy_range = energy_range
        self.price_fraction = price_fraction_choice

    def event_tick(self, *, area):
        if random.random() <= self.offer_chance:
            energy = random.randint(*self.energy_range)
            time, market = random.choice(list(area.markets.items()))
            offer = market.offer(
                energy,
                energy / random.choice(self.price_fraction),
                self.owner.name
            )
            self.log.info("Offering %s @ %s", offer, time.strftime('%H:%M'))
