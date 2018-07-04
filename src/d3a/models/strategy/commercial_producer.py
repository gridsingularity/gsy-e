import sys
from d3a.models.strategy import ureg, Q_

from d3a.models.strategy.base import BaseStrategy


class CommercialStrategy(BaseStrategy):
    parameters = ('energy_rate',)

    def __init__(self, energy_rate=None):
        if energy_rate is not None and energy_rate < 0:
            raise ValueError("Energy price should be positive.")
        super().__init__()
        if energy_rate is None:
            self.energy_rate = Q_(0, (ureg.EUR_cents / ureg.kWh))
        else:
            self.energy_rate = Q_(energy_rate, (ureg.EUR_cents / ureg.kWh))
        self.energy_per_slot_wh = Q_(int(sys.maxsize), ureg.kWh)

    def _markets_to_offer_on_activate(self):
        return list(self.area.markets.values())

    def event_activate(self):
        if self.energy_rate.m is None:
            self.energy_rate.m = self.area.config.market_maker_rate
        # That's usual an init function but the markets aren't open during the init call
        for market in self._markets_to_offer_on_activate():
            market.offer(
                self.energy_per_slot_wh.m * self.energy_rate.m,
                self.energy_per_slot_wh.m,
                self.owner.name
            )

    def event_trade(self, *, market, trade):
        # If trade happened post a new offer
        if self.owner.name == trade.seller:
            market.offer(
                self.energy_per_slot_wh.m * self.energy_rate.m,
                self.energy_per_slot_wh.m,
                self.owner.name
            )

    def event_market_cycle(self):
        # Post new offers
        market = list(self.area.markets.values())[-1]
        market.offer(
            self.energy_per_slot_wh.m * self.energy_rate.m,
            self.energy_per_slot_wh.m,
            self.owner.name
        )
