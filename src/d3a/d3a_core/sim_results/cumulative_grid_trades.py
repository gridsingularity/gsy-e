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
from d3a.d3a_core.sim_results.area_statistics import accumulate_grid_trades_all_devices, \
    generate_cumulative_grid_trades_for_all_areas
from d3a_interface.constants_limits import ConstSettings


def export_cumulative_grid_trades(area, accumulated_trades_redis, past_market_types):
    accumulated_trades = \
        accumulate_grid_trades_all_devices(area, accumulated_trades_redis, past_market_types)
    return accumulated_trades, generate_cumulative_grid_trades_for_all_areas(accumulated_trades,
                                                                             area, {})


class CumulativeGridTrades:
    def __init__(self):
        self.current_trades = {}
        self.current_balancing_trades = {}
        self.accumulated_trades = {}
        self.accumulated_balancing_trades = {}

    def update(self, area):
        self.accumulated_trades, self.current_trades = \
            export_cumulative_grid_trades(area, self.accumulated_trades,
                                          "current_market")

        if ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
            self.accumulated_balancing_trades, self.current_balancing_trades = \
                export_cumulative_grid_trades(area, self.accumulated_balancing_trades,
                                              "current_balancing_market")
