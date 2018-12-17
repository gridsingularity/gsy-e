"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
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
