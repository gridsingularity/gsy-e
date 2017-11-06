from typing import Dict, Any  # noqa

from d3a.exceptions import MarketException
from d3a.models.strategy.base import BaseStrategy


class FacebookDeviceStrategy(BaseStrategy):

    def __init__(self, avg_power, hrs_per_day, consolidated_cycle=None):
        self.avg_power = avg_power  # Average power in watts
        self.hrs_per_day = hrs_per_day  # Hrs the device is charged per day
        # consolidated_cycle is KWh energy consumed for the entire year
        self.consolidated_cycle = consolidated_cycle
        self.open_spot_markets = []

    def event_activate(self):
        self.open_spot_markets = list(self.area.markets.values())

    def event_tick(self, *, area):
        min_device_energy = self.calculate_daily_energy_req()
        for market in self.open_spot_markets:
            for offer in market.sorted_offers:
                if offer.energy * 1000 >= min_device_energy:
                    try:
                        self.accept_offer(market, offer)
                        self.log.debug("Buying %s", offer)
                        break
                    except MarketException:
                        self.log.critical("An Error occurred while buying an offer")

    def event_market_cycle(self):
        self.open_spot_markets = list(self.area.markets.values())

    # Returns energy in watt-hours at present
    def calculate_daily_energy_req(self):

        if self.consolidated_cycle:
            return (self.consolidated_cycle / 365) * 1000
        else:
            return self.avg_power * self.hrs_per_day
