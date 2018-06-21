import random
import sys
from d3a.models.strategy import ureg, Q_
from pendulum.interval import Interval

from d3a.exceptions import MarketException
from d3a.models.state import LoadState
from d3a.models.strategy.base import BaseStrategy


class LoadHoursStrategy(BaseStrategy):
    parameters = ('avg_power_W', 'hrs_per_day', 'hrs_of_day', 'acceptable_energy_rate')

    def __init__(self, avg_power_W, hrs_per_day=None, hrs_of_day=None, random_factor=0,
                 daily_budget=None, acceptable_energy_rate=sys.maxsize):
        super().__init__()
        self.state = LoadState()
        self.avg_power_W = Q_(avg_power_W, ureg.W)

        # consolidated_cycle is KWh energy consumed for the entire year
        self.daily_energy_required = None
        # Random factor to modify buying
        self.random_factor = random_factor
        # Budget for a single day in eur
        self.daily_budget = daily_budget * 100 if daily_budget is not None else None
        # Energy consumed during the day ideally should not exceed daily_energy_required
        self.energy_per_slot_Wh = None
        self.energy_requirement = 0
        self.max_acceptable_energy_price = 10**20
        # In ct. / kWh
        self.acceptable_energy_rate = Q_(acceptable_energy_rate, (ureg.EUR_cents/ureg.kWh))
        # be a parameter on the constructor or if we want to deal in percentages
        if hrs_per_day is None:
            hrs_per_day = len(hrs_of_day)
        if hrs_of_day is None:
            hrs_of_day = list(range(24))

        self.hrs_of_day = hrs_of_day
        self.hrs_per_day = hrs_per_day

        if not all([0 <= h <= 23 for h in hrs_of_day]):
            raise ValueError("Hrs_of_day list should contain integers between 0 and 23.")

        if len(hrs_of_day) < hrs_per_day:
            raise ValueError("Length of list 'hrs_of_day' must be greater equal 'hrs_per_day'")

    def event_activate(self):
        self.energy_per_slot_Wh = (self.avg_power_W /
                                   (Interval(hours=1)/self.area.config.slot_length))
        self.energy_per_slot_Wh = Q_(self.energy_per_slot_Wh.m, ureg.Wh)
        self.daily_energy_required = self.avg_power_W * self.hrs_per_day
        if self.daily_budget:
            self.max_acceptable_energy_price = (
                self.daily_budget / self.daily_energy_required * 1000
            )
        self._update_energy_requirement()

    def _find_acceptable_offer(self, market):
        offers = market.most_affordable_offers
        return random.choice(offers)

    def event_tick(self, *, area):

        if self.energy_requirement <= 0:
            return

        markets = []
        for time, market in self.area.markets.items():
            if self._allowed_operating_hours(time.hour):
                markets.append(market)
        if not markets:
            return
        if self._allowed_operating_hours(self.area.now.hour):
            try:
                market = list(self.area.markets.values())[0]
                if len(market.sorted_offers) < 1:
                    return

                acceptable_offer = self._find_acceptable_offer(market)
                if acceptable_offer and \
                        ((acceptable_offer.price/acceptable_offer.energy) <
                         self.acceptable_energy_rate.m):
                    max_energy = self.energy_requirement / 1000
                    if acceptable_offer.energy > max_energy:
                        self.accept_offer(market, acceptable_offer, energy=max_energy)
                        self.energy_requirement = 0
                        self.hrs_per_day -= self._operating_hours(max_energy)
                    else:
                        self.accept_offer(market, acceptable_offer)
                        self.energy_requirement -= acceptable_offer.energy * 1000
                        self.hrs_per_day -= self._operating_hours(acceptable_offer.energy)
            except MarketException:
                self.log.exception("An Error occurred while buying an offer")

    def _allowed_operating_hours(self, time):
        return time in self.hrs_of_day and self.hrs_per_day > 0

    def _operating_hours(self, energy):
        return (((energy * 1000) / self.energy_per_slot_Wh.m)
                * (self.area.config.slot_length / Interval(hours=1)))

    def _update_energy_requirement(self):
        self.energy_requirement = 0
        if self._allowed_operating_hours(self.area.now.hour):
            energy_per_slot = self.energy_per_slot_Wh.m
            if self.random_factor:
                energy_per_slot += energy_per_slot * random.random() * self.random_factor
            self.energy_requirement += energy_per_slot
        self.state.record_desired_energy(self.area, self.energy_requirement)

    def event_market_cycle(self):
        self._update_energy_requirement()


class CellTowerLoadHoursStrategy(LoadHoursStrategy):
    pass
