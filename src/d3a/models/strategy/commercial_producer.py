import sys
from d3a.models.strategy import ureg, Q_

from d3a.models.strategy.base import BaseStrategy


class CommercialStrategy(BaseStrategy):
    parameters = ('energy_rate',)

    def __init__(self, energy_rate=None):
        if energy_rate is not None and energy_rate < 0:
            raise ValueError("Energy rate should be positive.")
        super().__init__()
        self.energy_per_slot_kWh = Q_(int(sys.maxsize), ureg.kWh)
        self.energy_rate = energy_rate

    def _markets_to_offer_on_activate(self):
        return self.area.markets.values()

    def event_activate(self):
        # That's usually an init function but the markets aren't open during the init call
        for market in self._markets_to_offer_on_activate():
            self.offer_energy(market)

    def event_trade(self, *, market, trade):
        # If trade happened post a new offer
        if self.owner.name == trade.seller:
            self.offer_energy(market)

    def event_market_cycle(self):
        # Post new offers
        market = list(self.area.markets.values())[-1]
        self.offer_energy(market)

    def offer_energy(self, market):
        if self.energy_rate is None:
            market.offer(
                self.energy_per_slot_kWh.m *
                self.area.config.market_maker_rate[market.time_slot.hour],
                self.energy_per_slot_kWh.m,
                self.owner.name
            )
        else:
            market.offer(
                self.energy_per_slot_kWh.m * self.energy_rate,
                self.energy_per_slot_kWh.m,
                self.owner.name
            )
