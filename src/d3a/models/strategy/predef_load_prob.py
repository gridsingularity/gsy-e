import random

from d3a.exceptions import MarketException
from d3a.models.strategy.const import ConstSettings
from d3a.models.strategy.storage import StorageStrategy


class PredefLoadProbStrategy(StorageStrategy):
    parameters = ('risk', 'max_consumption')

    # max_consumption is the maximal possible consumption of the load
    def __init__(self, risk=ConstSettings.GeneralSettings.DEFAULT_RISK, max_consumption=200):
        super().__init__()
        self.risk = risk
        self.bought_in_market = set()
        self.max_consumption = max_consumption

    def event_tick(self, *, area):
        # Only trade after the second tick
        tick_in_slot = area.current_tick % area.config.ticks_per_slot
        if tick_in_slot < 3:
            return

        if self.risk is 0:
            # House is off Grid, so no interaction with the market
            pass

        elif self.risk is 1:
            self.not_home()

        elif self.risk is 100:
            self.home()

    def not_home(self):
        # Buy permanently X amount of energy: heating costs, standby devices etc
        # This equals the households consumption when no one is awake
        self.buy_energy(ConstSettings.PredefinedLoadSettings.MIN_HOUSEHOLD_CONSUMPTION)

    def home(self):
        # we pick the Minimal consumption plus some random additional energy
        needed_energy = ConstSettings.PredefinedLoadSettings.MIN_HOUSEHOLD_CONSUMPTION + \
                        (self.max_consumption * (random.randint(20, 100) / 100))
        self.buy_energy(needed_energy)

    def buy_energy(self, energy):
        if energy is 0:
            pass

        try:
            for market in self.area.markets.values():
                if market in self.bought_in_market:
                    continue
                for offer in market.sorted_offers:
                    # If offer is too small buy it and recall the function with the remaining
                    # needed energy
                    if offer.energy < energy / 1000:
                        try:
                            self.accept_offer(market, offer)
                            self.bought_in_market.add(market)
                            self.buy_energy(energy - offer.energy)
                        except MarketException:
                            # Offer already gone etc., use next one.
                            continue
                    # If offer.energy >= energy buy the offer and end buying process
                    try:
                        self.accept_offer(market, offer)
                        self.bought_in_market.add(market)
                        break
                    except MarketException:
                        # Offer already gone etc., use next one.
                        continue

        except IndexError:
            pass
