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
from d3a.models.strategy.storage import StorageStrategy

"""
Example file for StorageStrategy.
Is also used for integrationtest.
"""


class CustomStorageStrategy(StorageStrategy):

    def calculate_energy_to_buy(self, energy):
        """
        Copy of original code
        Greedy storage, as it buys maximal available and needed energy
        :return:
        """
        return self.state.clamp_energy_to_buy_kWh(energy)

    def calculate_energy_to_sell(self, energy, target_market):
        """
        Copy of original code
        """
        energy = self.state.clamp_energy_to_sell_kWh(energy, target_market.time_slot)
        return energy

    def calculate_selling_rate(self, market):
        """
        Return initial selling rate (market maker rate)
        """

        return self.area.config.market_maker_rate[market.time_slot]

    def decrease_energy_price_over_ticks(self, market):
        """
        Decreases the offer rate by 0.1 ct/kWh per tick
        """

        reduced_rate = 5
        # example for determining the current tick number:
        current_tick_number = self.area.current_tick % self.area.config.ticks_per_slot
        if current_tick_number >= 0:
            if reduced_rate < self.final_selling_rate:
                reduced_rate = self.final_selling_rate
            self._decrease_offer_price(self.area.next_market, reduced_rate)

    def select_market_to_sell(self):
        """
        Sell on the most recent future market
        """
        return [self.area.next_market]

    def update_posted_bids_over_ticks(self, market):
        """
        Copy of the original code
        This is  not tested in the integrationtest (Scenario: "Custom storage works as expected")
        Because this functionality is already tests in the StorageStrategy
        """
        # Decrease the selling price over the ticks in a slot
        current_tick_number = self.area.current_tick % self.area.config.ticks_per_slot
        elapsed_seconds = current_tick_number * self.area.config.tick_length.seconds
        if elapsed_seconds > self._increase_rate_timepoint_s:
            self._increase_rate_timepoint_s += self._increase_frequency_s
            self._update_posted_bids(market, current_tick_number)
