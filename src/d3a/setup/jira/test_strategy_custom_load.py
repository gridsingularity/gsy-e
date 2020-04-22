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
from d3a.models.strategy.load_hours import LoadHoursStrategy

"""
Example file for CustomLoadStrategy.
Is also used for integrationtest.
"""


class CustomLoadStrategy(LoadHoursStrategy):

    def update_posted_bids_over_ticks(self, market):
        """
        Copy of original code
        """
        # Decrease the selling price over the ticks in a slot
        current_tick_number = self.area.current_tick_in_slot % self.area.config.ticks_per_slot
        elapsed_seconds = current_tick_number * self.area.config.tick_length.seconds
        if elapsed_seconds > self._increase_rate_timepoint_s[market.time_slot]:
            self._increase_rate_timepoint_s[market.time_slot] += self._increase_frequency_s
            existing_bids = list(self.get_posted_bids(market))
            for bid in existing_bids:
                if bid.id in market.bids.keys():
                    bid = market.bids[bid.id]
                market.delete_bid(bid.id)
                self.remove_bid_from_pending(market, bid.id)
                self.post_bid(market,
                              bid.energy * self._get_current_energy_rate(current_tick_number,
                                                                         market),
                              bid.energy)
