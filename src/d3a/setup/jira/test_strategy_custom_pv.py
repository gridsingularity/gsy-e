from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy import ureg, Q_
from d3a.exceptions import MarketException

"""
Example file for CustomPvStrategy
Is also used for integrationtest
"""


class CustomPvStrategy(PVStrategy):

    def produced_energy_forecast_real_data(self):
        """
        Returnes flat PV production curve.
        """

        for slot_time in [
                    self.area.now + (self.area.config.slot_length * i)
                    for i in range(
                        (
                                    self.area.config.duration
                                    + (
                                            self.area.config.market_count *
                                            self.area.config.slot_length)
                        ) // self.area.config.slot_length)
                    ]:
            self.energy_production_forecast_kWh[slot_time] = 100

    def calculate_initial_sell_rate(self, current_time_h):
        """
        Sets the initial sell rate to the market_maker_rate
        """

        return Q_(self.area.config.market_maker_rate[current_time_h],
                  ureg.EUR_cents / ureg.kWh)

    def decrease_energy_price_over_ticks(self):
        """
        Decreases the offer rate by 0.1 ct/kWh per tick
        """
        decrease_rate_per_tick = 0.1
        next_market = list(self.area.markets.values())[0]
        if next_market not in self.offers.open.values():
            return

        for offer, iterated_market in self.offers.open.items():
            if iterated_market != next_market:
                continue
            try:
                iterated_market.delete_offer(offer.id)
                new_offer = iterated_market.offer(
                    (offer.price - (offer.energy *
                                    decrease_rate_per_tick)),
                    offer.energy,
                    self.owner.name
                )
                if (new_offer.price/new_offer.energy) < self.min_selling_rate.m:
                    new_offer.price = self.min_selling_rate.m * new_offer.energy
                self.offers.replace(offer, new_offer, iterated_market)

            except MarketException:
                continue
