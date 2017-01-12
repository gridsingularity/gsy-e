from d3a.exceptions import MarketException
from d3a.models.strategy.base import BaseStrategy


class PermanentLoadStrategy(BaseStrategy):
    def __init__(self, energy_wh=100, pre_buy_range=4):
        super().__init__()
        self.energy_wh = energy_wh
        self.pre_buy_range = pre_buy_range

        self.bought_in_market = set()

    def event_tick(self, *, area):
        try:
            for i, market in enumerate(area.markets.values()):
                if i + 1 > self.pre_buy_range:
                    break
                if market in self.bought_in_market:
                    continue
                for offer in market.sorted_offers:
                    if offer.energy < self.energy_wh / 1000:
                        continue
                    try:
                        self.accept_offer(market, offer)
                        self.log.info("Buying %s", offer)
                        self.bought_in_market.add(market)
                        break
                    except MarketException:
                        # Offer already gone etc., use next one.
                        continue

        except IndexError:
            pass
