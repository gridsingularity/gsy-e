import random

from first import first
from pendulum.interval import Interval

from d3a.exceptions import MarketException
from d3a.models.strategy.base import BaseStrategy


class FacebookDeviceStrategy(BaseStrategy):
    def __init__(self, avg_power, hrs_per_day, hrs_of_day=(0, 23), random_factor=0,
                 daily_budget=None):
        super().__init__()
        self.avg_power = avg_power  # Average power in watts
        self.hrs_per_day = hrs_per_day  # Hrs the device is charged per day
        # consolidated_cycle is KWh energy consumed for the entire year
        self.daily_energy_required = self.avg_power * self.hrs_per_day
        # Random factor to modify buying
        self.random_factor = random_factor
        # Budget for a single day in eur
        self.daily_budget = daily_budget * 100
        # Energy consumed during the day ideally should not exceed daily_energy_required
        self.energy_per_slot = None
        self.energy_requirement = 0
        # In ct. / kWh
        self.max_acceptable_energy_price = 10**20
        if self.daily_budget:
            self.max_acceptable_energy_price = (
                self.daily_budget / self.daily_energy_required * 1000
            )
        # be a parameter on the constructor or if we want to deal in percentages
        self.hrs_of_day = hrs_of_day
        active_hours_count = (hrs_of_day[1] - hrs_of_day[0] + 1)
        if hrs_per_day > active_hours_count:
            raise ValueError(
                "Device can't be active more hours per day than active hours: {} > {}".format(
                    hrs_per_day,
                    active_hours_count
                )
            )
        active_hours = set()
        while len(active_hours) < hrs_per_day:
            active_hours.add(random.randrange(hrs_of_day[0], hrs_of_day[1] + 1))
        self.active_hours = active_hours

    def event_activate(self):
        self.energy_per_slot = (
            self.daily_energy_required
            /
            (self.hrs_per_day * Interval(hours=1) / self.area.config.slot_length)
        )

    def event_tick(self, *, area):
        if self.energy_requirement <= 0:
            return

        markets = []
        for time, market in self.area.markets.items():
            if time.hour in self.active_hours:
                markets.append(market)
        if not markets:
            return

        try:
            # Don't have an idea whether we need a price mechanism, at this stage the cheapest
            # offers available in the markets is picked up
            cheapest_offer, market = first(
                sorted(
                    [
                        (offer, market) for market in markets
                        for offer in market.sorted_offers
                        if (
                            offer.energy <= self.energy_requirement / 1000
                            and offer.price / offer.energy <= self.max_acceptable_energy_price
                        )
                    ],
                    key=lambda o: o[0].price / o[0].energy
                ),
                default=(None, None)
            )
            if cheapest_offer:
                self.accept_offer(market, cheapest_offer)
                self.energy_requirement -= cheapest_offer.energy * 1000
        except MarketException:
            self.log.exception("An Error occurred while buying an offer")

    def event_market_cycle(self):
        if self.area.now.hour in self.active_hours:
            energy_per_slot = self.energy_per_slot
            if self.random_factor:
                energy_per_slot += energy_per_slot * random.random() * self.random_factor
            self.energy_requirement += energy_per_slot
