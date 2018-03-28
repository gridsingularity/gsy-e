import random

from pendulum.interval import Interval

from d3a.exceptions import MarketException
from d3a.models.state import LoadState
from d3a.models.strategy.base import BaseStrategy


class LoadHoursStrategy(BaseStrategy):
    def __init__(self, avg_power, hrs_per_day, hrs_of_day=(0, 23), random_factor=0,
                 daily_budget=None, acceptable_energy_rate=10 ** 20):
        super().__init__()
        self.state = LoadState()
        self.avg_power_in_Wh = avg_power
        self.avg_power = None
        self.hrs_per_day = hrs_per_day  # Hrs the device is charged per day
        # consolidated_cycle is KWh energy consumed for the entire year
        self.daily_energy_required = None
        # Random factor to modify buying
        self.random_factor = random_factor
        # Budget for a single day in eur
        self.daily_budget = daily_budget * 100 if daily_budget is not None else None
        # Energy consumed during the day ideally should not exceed daily_energy_required
        self.energy_per_slot = None
        self.energy_requirement = 0
        # In ct. / kWh
        self.acceptable_energy_rate = acceptable_energy_rate
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
        self.avg_power = (self.avg_power_in_Wh /
                          (Interval(hours=1) / self.area.config.slot_length)
                          )
#        self.acceptable_energy_rate = self.acceptable_energy_rate/1000
        self.daily_energy_required = self.avg_power * self.hrs_per_day
        # Avg_power is actually the power per slot, since it is calculated by dividing the
        # avg_power_in_Wh by the number of slots per hour
        self.energy_per_slot = self.avg_power

    def event_tick(self, *, area):
        if self.energy_requirement <= 0:
            return

        markets = []
        for time, market in self.area.markets.items():
            if time.hour in self.active_hours:
                markets.append(market)
        if not markets:
            return

        if self.area.now.hour in self.active_hours:
            try:
                market = list(self.area.markets.values())[0]
                acceptable_offer = market.sorted_offers[0]

                if acceptable_offer and \
                        ((acceptable_offer.price/acceptable_offer.energy) <
                         self.acceptable_energy_rate):
                    max_energy = self.energy_requirement / 1000
                    if acceptable_offer.energy > max_energy:
                        self.accept_offer(market, acceptable_offer, energy=max_energy)
                        self.energy_requirement = 0
                    else:
                        self.accept_offer(market, acceptable_offer)
                        self.energy_requirement -= acceptable_offer.energy * 1000
            except MarketException:
                self.log.exception("An Error occurred while buying an offer")

    def event_market_cycle(self):
        if self.area.now.hour in self.active_hours:
            self.state.record_desired_energy(self.area, self.avg_power)
            energy_per_slot = self.energy_per_slot
            if self.random_factor:
                energy_per_slot += energy_per_slot * random.random() * self.random_factor
            self.energy_requirement += energy_per_slot
