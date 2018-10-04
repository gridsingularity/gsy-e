from d3a.models.strategy.pv import PVStrategy

"""
Example file for CustomPvStrategy.
Is also used for integrationtest.
"""


class CustomPvStrategy(PVStrategy):

    def produced_energy_forecast_kWh(self):
        """
        Returns flat PV production curve.
        """

        for slot_time in self.energy_production_forecast_kWh.keys():
            self.energy_production_forecast_kWh[slot_time] = 100

    def calculate_initial_sell_rate(self, current_time_h):
        """
        Sets the initial sell rate to the market_maker_rate
        """

        return self.area.config.market_maker_rate[current_time_h]

    def decrease_energy_price_over_ticks(self, market):
        """
        Decreases the offer rate by 0.1 ct/kWh per tick
        """

        decrease_rate_per_tick = 0.1
        # example for determining the current tick number:
        current_tick_number = self.area.current_tick % self.area.config.ticks_per_slot
        if current_tick_number >= 0:
            self._decrease_offer_price(self.area.next_market, decrease_rate_per_tick)
