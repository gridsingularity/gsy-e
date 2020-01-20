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
from d3a.d3a_core.sim_results.area_statistics import export_cumulative_grid_trades, \
    export_cumulative_grid_trades_redis, export_cumulative_loads, MarketPriceEnergyDay, \
    generate_inter_area_trade_details
from d3a.d3a_core.sim_results.file_export_endpoints import FileExportEndpoints
from d3a.d3a_core.sim_results.stats import MarketEnergyBills
from d3a.d3a_core.sim_results.device_statistics import DeviceStatistics
from d3a.d3a_core.sim_results.export_unmatched_loads import MarketUnmatchedLoads
from d3a_interface.constants_limits import ConstSettings

from statistics import mean
from pendulum import duration

_NO_VALUE = {
    'min': None,
    'avg': None,
    'max': None
}


class SimulationEndpointBuffer:
    def __init__(self, job_id, initial_params, area):
        self.job_id = job_id
        self.random_seed = initial_params["seed"] if initial_params["seed"] is not None else ''
        self.status = {}
        self.eta = duration(seconds=0)
        self.market_unmatched_loads = MarketUnmatchedLoads(area)
        self.cumulative_loads = {}
        self.price_energy_day = MarketPriceEnergyDay()
        self.tree_summary = TreeSummary()
        self.market_bills = MarketEnergyBills()
        self.balancing_bills = MarketEnergyBills(is_spot_market=False)
        self.cumulative_grid_trades = CumulativeGridTrades()
        self.trade_details = {}
        self.device_statistics = DeviceStatistics()
        self.file_export_endpoints = FileExportEndpoints()

        self.last_unmatched_loads = {}

    def generate_result_report(self):
        redis_results = {
            "job_id": self.job_id,
            "random_seed": self.random_seed,
            "cumulative_loads": self.cumulative_loads,
            "cumulative_grid_trades": self.cumulative_grid_trades.current_trades_redis,
            "bills": self.market_bills.bills_redis_results,
            "tree_summary": self.tree_summary.current_results_redis,
            "status": self.status,
            "eta_seconds": self.eta.seconds,
        }

        if ConstSettings.GeneralSettings.REDIS_PUBLISH_FULL_RESULTS:
            redis_results.update({
                "unmatched_loads": self.market_unmatched_loads.unmatched_loads_uuid,
                "price_energy_day": self.price_energy_day.redis_output,
                "device_statistics": self.device_statistics.flat_stats_time_str,
                "energy_trade_profile": self.file_export_endpoints.traded_energy_profile_redis,
            })
        else:
            redis_results.update({
                "last_unmatched_loads": self.market_unmatched_loads.last_unmatched_loads,
                "last_energy_trade_profile": self.file_export_endpoints.traded_energy_current,
                "last_price_energy_day": self.price_energy_day.redis_output,
                "last_device_statistics": self.device_statistics.current_stats_time_str
            })

        return redis_results

    def generate_json_report(self):
        return {
            "job_id": self.job_id,
            "random_seed": self.random_seed,
            "unmatched_loads": self.market_unmatched_loads.unmatched_loads,
            "cumulative_loads": self.cumulative_loads,
            "price_energy_day": self.price_energy_day.csv_output,
            "cumulative_grid_trades": self.cumulative_grid_trades.current_trades_redis,
            "bills": self.market_bills.bills_results,
            "tree_summary": self.tree_summary.current_results,
            "status": self.status,
            "device_statistics": self.device_statistics.device_stats_time_str,
            "energy_trade_profile": self.file_export_endpoints.traded_energy_profile,
        }

    def update_stats(self, area, simulation_status, eta):
        self.status = simulation_status
        self.eta = eta
        self.cumulative_loads = export_cumulative_loads(area)

        self.cumulative_grid_trades.update(area)

        self.market_bills.update(area)
        self.balancing_bills.update(area)

        self.trade_details = generate_inter_area_trade_details(area, "past_markets")

        self.file_export_endpoints(area)
        self.market_unmatched_loads.update_unmatched_loads(area)
        self.device_statistics.update(area)

        self._update_price_energy_day_tree_summary(area)

        self.generate_result_report()

    def _update_price_energy_day_tree_summary(self, area):
        # Update of the price_energy_day endpoint should always precede tree-summary.
        # The reason is that the price_energy_day data are used when calculating the
        # tree-summary data.
        self.price_energy_day.update(area)
        self.tree_summary.update(area, self.price_energy_day.csv_output)


class TreeSummary:
    def __init__(self):
        self.current_results = {}
        self.current_results_redis = {}

    def update(self, area, price_energy_day_csv_output):
        price_energy_list = price_energy_day_csv_output

        def calculate_prices(key, functor):
            if area.name not in price_energy_list:
                return 0.

            energy_prices = [
                price_energy[key]
                for price_energy in price_energy_list[area.name]["price-energy-day"]
            ]
            return round(functor(energy_prices), 2) if len(energy_prices) > 0 else 0.0

        self.current_results[area.slug] = {
            "min_trade_price": calculate_prices("min_price", min),
            "max_trade_price": calculate_prices("max_price", max),
            "avg_trade_price": calculate_prices("av_price", mean),
        }
        self.current_results_redis[area.uuid] = self.current_results[area.slug]
        for child in area.children:
            if child.children:
                self.update(child, price_energy_day_csv_output)


class CumulativeGridTrades:
    def __init__(self):
        self.current_trades = {}
        self.current_trades_redis = {}
        self.current_balancing_trades = {}
        self.accumulated_trades = {}
        self.accumulated_trades_redis = {}
        self.accumulated_balancing_trades = {}

    def update(self, area):
        market_type = \
            "past_markets" if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS else "current_market"
        balancing_market_type = "past_balancing_markets" \
            if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS \
            else "current_balancing_market"

        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            self.accumulated_trades = {}
            self.accumulated_trades_redis = {}
            self.accumulated_balancing_trades = {}

        self.accumulated_trades_redis, self.current_trades_redis = \
            export_cumulative_grid_trades_redis(area, self.accumulated_trades_redis,
                                                market_type)
        self.accumulated_trades, self.current_trades = \
            export_cumulative_grid_trades(area, self.accumulated_trades,
                                          market_type, all_devices=True)
        self.accumulated_balancing_trades, self.current_balancing_trades = \
            export_cumulative_grid_trades(area, self.accumulated_balancing_trades,
                                          balancing_market_type)
