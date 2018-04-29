import random
import csv

from d3a.exceptions import MarketException
from d3a.models.state import LoadState
from d3a.models.strategy.base import BaseStrategy


class DefinedLoadStrategy(BaseStrategy):
    def __init__(self, path, acceptable_energy_rate=10 ** 20):
        super().__init__()
        self.state = LoadState()
        self.data = {}
        self.readCSV(path)
        # In Wh oer slot
        self.energy_requirement = 0
        # In ct. / kWh
        self.acceptable_energy_rate = acceptable_energy_rate

    def readCSV(self, path):
        with open(path) as csvfile:
            next(csvfile)
            csv_rows = csv.reader(csvfile, delimiter=';')
            for row in csv_rows:
                k, v = row
                self.data[k] = float(v)

    def event_activate(self):
        self._update_energy_requirement()

    def _find_acceptable_offer(self, market):
        offers = market.most_affordable_offers
        return random.choice(offers)

    def event_tick(self, *, area):
        if self.energy_requirement <= 0:
            return

        markets = []
        for time, market in self.area.markets.items():
            if time.format('%H:%M') in self.data.keys():
                print("Inside Market")
                markets.append(market)
        if not markets:
            return

        if self.data[self.area.next_market.time_slot.format('%H:%M')] != 0:
            try:
                market = list(self.area.markets.values())[0]
                if len(market.sorted_offers) < 1:
                    return
                acceptable_offer = self._find_acceptable_offer(market)
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

    def _update_energy_requirement(self):
        self.energy_requirement = 0
        if self.data[self.area.next_market.time_slot.format('%H:%M')] != 0:
            energy_per_slot = self.data[self.area.next_market.time_slot.format('%H:%M')]
            self.energy_requirement = energy_per_slot
        self.state.record_desired_energy(self.area, self.energy_requirement)

    def event_market_cycle(self):
        self._update_energy_requirement()
