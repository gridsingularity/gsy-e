import math

from d3a.exceptions import MarketException
from d3a.models.strategy.const import DEFAULT_RISK, MIN_HOUSEHOLD_CONSUMPTION
from d3a.models.strategy.storage import StorageStrategy

if __name__ == '__main__':
    class PredefLoadHouseholdStrategy(StorageStrategy):
        def __init__(self, risk=DEFAULT_RISK):
            super().__init__()
            self.risk = risk
            self.bought_in_market = set()

        def event_tick(self, *, area):
            # Only trade after the second tick
            tick_in_slot = area.current_tick % area.config.ticks_per_slot
            if tick_in_slot < 3:
                return

            # This gives us a pendulum object with today 0 o'clock
            midnight = self.area.now.start_of("day").hour_(0)
            difference_to_midnight_in_minutes = self.area.now.diff(midnight).in_minutes()

            if self.risk is 0:
                # House is off Grid, so no interaction with the market
                pass

            elif self.risk is 1:
                self.not_home()

            elif self.risk is 100:
                self.home(difference_to_midnight_in_minutes)

        def not_home(self):
            # Buy permanently X amount of energy: heating costs, standby devices etc
            # This equals the households consumption when no one is awake
            self.home(0)

        def home(self, time):
            # TODO: Find better description of energy consumption over on day than using
            # TODO: two gaussian distribution
            # Buy Energy X amount of energy: light electronics etc.
            # Used as reverence: https://nelsonslog.wordpress.com/2012/01/31/energy-usage-notes/
            if time <= (6 * 60):
                # needed energy equals 0.7 wKH
                needed_energy = MIN_HOUSEHOLD_CONSUMPTION
                self.buy_energy(needed_energy)

            if (6 * 60) < time <= (11.5 * 60):
                # needed energy is a gaussian with x_0= 10:30hr and sigma = 1hr
                needed_energy = MIN_HOUSEHOLD_CONSUMPTION * (
                    math.exp(- ((time - (10.5 * 60)) ** 2) / 2 * ((1 * 60) ** 2))
                )
                self.buy_energy(needed_energy)

            if (11.5 * 60) < time <= (18 * 60):
                # Needed energy is minimum load plus a linear growing factor over elapsed time,
                # that ends at 18hr with a total additional consumption of 50 Wh
                needed_energy = MIN_HOUSEHOLD_CONSUMPTION + (time - (12 * 60)) * (50 / (6 * 60))
                self.buy_energy(needed_energy)

            if (18 * 60) < time <= ((23 * 60) + 59):
                needed_energy = MIN_HOUSEHOLD_CONSUMPTION * (
                    math.exp(- ((time - (21 * 60)) ** 2) / 2 * ((1.5 * 60) ** 2))
                )
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
