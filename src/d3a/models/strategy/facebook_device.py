import random

from first import first
from pendulum.interval import Interval

from d3a.exceptions import MarketException
from d3a.models.strategy.base import BaseStrategy


class FacebookDeviceStrategy(BaseStrategy):
    def __init__(self, avg_power, hrs_per_day=None, hrs_of_day=(0, 23), consolidated_cycle=None,
                 random_factor=0):
        super().__init__()
        self.avg_power = avg_power  # Average power in watts
        if not hrs_per_day and not consolidated_cycle:
            raise ValueError("Either 'hrs_per_day' or 'consolidated_cycle' is required")
        self.hrs_per_day = hrs_per_day  # Hrs the device is charged per day
        # consolidated_cycle is KWh energy consumed for the entire year
        self.consolidated_cycle = consolidated_cycle
        self.daily_energy_required = self.calculate_daily_energy_req()
        # Energy consumed during the day ideally should not exceed daily_energy_required
        self.energy_bought_in_slot = 0
        self.energy_missing = 0
        self.energy_per_slot = None
        self.random_factor = random_factor
        # This is the minimum batch of energy that a device buys, please check whether this could
        # be a parameter on the constructor or if we want to deal in percentages
        self.min_energy_buy = 50  # 50 wh is the energy to buy each time for the device
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
        energy_to_buy = self.energy_per_slot
        if self.random_factor:
            energy_to_buy += energy_to_buy * random.random() * self.random_factor
        if self.energy_missing:
            energy_to_buy += self.energy_missing
            self.energy_missing = 0

        energy_to_buy -= self.energy_bought_in_slot

        if energy_to_buy < 0.0001:
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
                        if offer.energy <= energy_to_buy / 1000
                    ],
                    key=lambda o: o[0].price / o[0].energy
                ),
                default=(None, None)
            )
            if cheapest_offer:
                self.accept_offer(market, cheapest_offer)
                self.energy_bought_in_slot += energy_to_buy
        except MarketException:
            self.log.exception("An Error occurred while buying an offer")

    def event_market_cycle(self):
        self.energy_missing = 0
        should_buy = list(self.area.past_markets.keys())[-1].hour in self.active_hours
        if should_buy and self.energy_bought_in_slot < self.energy_per_slot:
            self.energy_missing = self.energy_per_slot - self.energy_bought_in_slot
        self.energy_bought_in_slot = 0

    # Returns daily energy required by the device in watt-hours at present
    def calculate_daily_energy_req(self):
        if self.consolidated_cycle:
            return (self.consolidated_cycle / 365) * 1000
        elif self.hrs_per_day:
            return self.avg_power * self.hrs_per_day
