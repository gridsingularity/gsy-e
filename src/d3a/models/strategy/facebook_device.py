import pendulum
from typing import Dict, Any  # noqa
from collections import OrderedDict
from d3a.exceptions import D3AException
from first import first

from d3a.exceptions import MarketException
from d3a.models.strategy.base import BaseStrategy


class FacebookDeviceStrategy(BaseStrategy):
    def __init__(self, avg_power, hrs_per_day=None, hrs_of_day=(0, 23), consolidated_cycle=None):
        super().__init__()
        self.avg_power = avg_power  # Average power in watts
        if not hrs_per_day and not consolidated_cycle:
            raise ValueError("Either 'hrs_per_day' or 'consolidated_cycle' is required")
        self.hrs_per_day = hrs_per_day  # Hrs the device is charged per day
        # consolidated_cycle is KWh energy consumed for the entire year
        self.consolidated_cycle = consolidated_cycle
        self.daily_energy_required = self.calculate_daily_energy_req()
        # Energy consumed during the day ideally should not exceed daily_energy_required
        self.energy_consumed = OrderedDict()  # type: Dict[Pendulum, float]
        self.midnight = None
        # This is the minimum batch of energy that a device buys, please check whether this could
        # be a parameter on the constructor or if we want to deal in percentages
        self.min_energy_buy = 50  # 50 wh is the energy to buy each time for the device
        self.hrs_of_day = hrs_of_day
        self.period_active = self.calculate_active_period()

    def event_activate(self):
        self.midnight = self.area.now.start_of("day").hour_(0)
        self.period_active = self.calculate_active_period()

    def event_tick(self, *, area):
        energy_to_buy = 0
        remaining_energy_required = self.remaining_energy_requirement()
        # remaining_energy_required <= 50
        if remaining_energy_required <= self.min_energy_buy:
            energy_to_buy = remaining_energy_required
        elif remaining_energy_required > self.min_energy_buy:
            energy_to_buy = self.min_energy_buy

        if energy_to_buy == 0.0:
            return
        markets = []
        for time, market in self.area.markets.items():
            if time in self.period_active:
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
                        if offer.energy <= energy_to_buy / 1000
                    ],
                    key=lambda o: o[0].price / o[0].energy
                ),
                default=(None, None)
            )
            if cheapest_offer:
                self.accept_offer(market, cheapest_offer)
                self.energy_consumed[pendulum.now()] = energy_to_buy
        except MarketException:
            self.log.exception("An Error occurred while buying an offer")

    def event_market_cycle(self):
        # Remove all dictionary entries of time, energy before midnight today
        for time, energy_value in self.energy_consumed.items():
            if time < self.midnight:
                del self.energy_consumed[time]

    # Returns daily energy required by the device in watt-hours at present
    def calculate_daily_energy_req(self):
        if self.consolidated_cycle:
            return (self.consolidated_cycle / 365) * 1000
        elif self.hrs_per_day:
            return self.avg_power * self.hrs_per_day

    # This function comes into picture if we decide to buy energy in percentages of the
    # total energy required for the day
    def calculate_percentage_of_energy_to_buy(self):
        pass

    # Returns the remaining energy required for the device on this day
    def remaining_energy_requirement(self):
        energy_consumed_today = 0  # energy consumed today or bought today
        for time, energy_value in self.energy_consumed.items():
            if time > self.midnight:
                energy_consumed_today += energy_value

        if energy_consumed_today >= self.daily_energy_required:
            return 0
        else:
            return self.daily_energy_required - energy_consumed_today

    def calculate_active_period(self):
        if self.hrs_of_day[0] >= self.hrs_of_day[1]:
            raise D3AException('Start hour cannot be greater than the end hour')
        else:
            # Instantiating a Period object for the hours the device is active
            # https://pendulum.eustace.io/docs/#period
            if self.midnight:
                return self.midnight.end_of("hour").hour_(self.hrs_of_day[1]).diff(
                    self.midnight.start_of("hour").hour_(self.hrs_of_day[0]))
