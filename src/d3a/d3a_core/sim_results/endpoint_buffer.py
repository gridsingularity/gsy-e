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
from d3a.d3a_core.sim_results.export_unmatched_loads import ExportUnmatchedLoads, \
    MarketUnmatchedLoads
from d3a_interface.constants_limits import ConstSettings
from d3a.constants import REDIS_PUBLISH_FULL_RESULTS
from d3a.d3a_core.util import round_floats_for_ui
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
        self.unmatched_loads = {}
        self.unmatched_loads_redis = {}
        self.export_unmatched_loads = ExportUnmatchedLoads(area)
        self.market_unmatched_loads = MarketUnmatchedLoads()
        self.cumulative_loads = {}
        self.price_energy_day = MarketPriceEnergyDay()
        self.cumulative_grid_trades = {}
        self.accumulated_trades = {}
        self.accumulated_trades_redis = {}
        self.accumulated_balancing_trades = {}
        self.cumulative_grid_trades_redis = {}
        self.cumulative_grid_balancing_trades = {}
        self.tree_summary = {}
        self.tree_summary_redis = {}
        self.market_bills = MarketEnergyBills()
        self.balancing_bills = MarketEnergyBills(is_spot_market=False)
        self.trade_details = {}
        self.device_statistics = DeviceStatistics()
        self.energy_trade_profile = {}
        self.energy_trade_profile_redis = {}
        self.last_energy_trade_profile = {}
        self.file_export_endpoints = FileExportEndpoints()

        self.last_unmatched_loads = {}

    def generate_result_report(self):
        redis_results = {
            "job_id": self.job_id,
            "random_seed": self.random_seed,
            "cumulative_loads": self.cumulative_loads,
            "cumulative_grid_trades": self.cumulative_grid_trades_redis,
            "bills": self.market_bills.bills_redis_results,
            "tree_summary": self.tree_summary_redis,
            "status": self.status,
            "eta_seconds": self.eta.seconds,
        }

        if REDIS_PUBLISH_FULL_RESULTS:
            redis_results.update({
                "unmatched_loads": self.unmatched_loads_redis,
                "price_energy_day": self.price_energy_day.redis_output,
                "device_statistics": self.device_statistics.flat_stats_time_str,
                "energy_trade_profile": self.energy_trade_profile_redis,
            })
        else:
            redis_results.update({
                "last_unmatched_loads": self.last_unmatched_loads,
                "last_energy_trade_profile": self.last_energy_trade_profile,
                "last_price_energy_day": self.price_energy_day.latest_output,
                "last_device_statistics": self.device_statistics.current_stats_time_str
            })
        return redis_results

    def generate_json_report(self):
        return {
            "job_id": self.job_id,
            "random_seed": self.random_seed,
            "unmatched_loads": self.unmatched_loads,
            "cumulative_loads": self.cumulative_loads,
            "price_energy_day": self.price_energy_day.csv_output,
            "cumulative_grid_trades": self.cumulative_grid_trades,
            "bills": self.market_bills.bills_results,
            "tree_summary": self.tree_summary,
            "status": self.status,
            "device_statistics": self.device_statistics.device_stats_time_str,
            "energy_trade_profile": self.energy_trade_profile,
        }

    def _update_unmatched_loads(self, area):
        if self.export_unmatched_loads.load_count == 0:
            self.unmatched_loads, self.unmatched_loads_redis =\
                self.market_unmatched_loads.write_none_to_unmatched_loads(area, {}, {})
        else:
            current_results, current_results_uuid = \
                self.export_unmatched_loads.get_current_market_results(
                    all_past_markets=ConstSettings.GeneralSettings.KEEP_PAST_MARKETS)

            if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
                self.unmatched_loads = current_results
                self.unmatched_loads_redis = current_results_uuid
            else:
                self.unmatched_loads, self.unmatched_loads_redis = \
                    self.market_unmatched_loads.update_and_get_unmatched_loads(
                        current_results, current_results_uuid)
                self.last_unmatched_loads = self.market_unmatched_loads._partial_unmatched_loads

    def _update_cumulative_grid_trades(self, area):
        market_type = \
            "past_markets" if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS else "current_market"
        balancing_market_type = "past_balancing_markets" \
            if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS \
            else "current_balancing_market"

        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            self.accumulated_trades = {}
            self.accumulated_trades_redis = {}
            self.accumulated_balancing_trades = {}

        self.accumulated_trades_redis, self.cumulative_grid_trades_redis = \
            export_cumulative_grid_trades_redis(area, self.accumulated_trades_redis,
                                                market_type)
        self.accumulated_trades, self.cumulative_grid_trades = \
            export_cumulative_grid_trades(area, self.accumulated_trades,
                                          market_type, all_devices=True)
        self.accumulated_balancing_trades, self.cumulative_grid_balancing_trades = \
            export_cumulative_grid_trades(area, self.accumulated_balancing_trades,
                                          balancing_market_type)

    def update_stats(self, area, simulation_status, eta):
        self.status = simulation_status
        self.eta = eta
        self._update_unmatched_loads(area)
        # Should always precede tree-summary update
        self.price_energy_day.update(area)
        self.cumulative_loads = {
            "price-currency": "Euros",
            "load-unit": "kWh",
            "cumulative-load-price": export_cumulative_loads(area)
        }

        self._update_cumulative_grid_trades(area)

        self.market_bills.update(area)
        self.balancing_bills.update(area)

        self._update_tree_summary(area)
        self.trade_details = generate_inter_area_trade_details(area, "past_markets")

        self.device_statistics.update(area)

        self.file_export_endpoints(area)
        self.energy_trade_profile = self.file_export_endpoints.traded_energy_profile
        self.energy_trade_profile_redis = self._round_energy_trade_profile(
            self.file_export_endpoints.traded_energy_profile_redis)

        self.last_energy_trade_profile = self._round_energy_trade_profile(
            self.file_export_endpoints.traded_energy_current)
        self.generate_result_report()

    def _update_tree_summary(self, area):
        price_energy_list = self.price_energy_day.csv_output

        def calculate_prices(key, functor):
            if area.name not in price_energy_list:
                return 0.
            energy_prices = [
                price_energy[key]
                for price_energy in price_energy_list[area.name]["price-energy-day"]
            ]
            return round(functor(energy_prices), 2) if len(energy_prices) > 0 else 0.0

        self.tree_summary[area.slug] = {
            "min_trade_price": calculate_prices("min_price", min),
            "max_trade_price": calculate_prices("max_price", max),
            "avg_trade_price": calculate_prices("av_price", mean),
        }
        self.tree_summary_redis[area.uuid] = self.tree_summary[area.slug]
        for child in area.children:
            if child.children:
                self._update_tree_summary(child)

    @classmethod
    def _round_energy_trade_profile(cls, profile):
        for k in profile.keys():
            for sold_bought in ['sold_energy', 'bought_energy']:
                if sold_bought not in profile[k]:
                    continue
                for dev in profile[k][sold_bought].keys():
                    for target in profile[k][sold_bought][dev].keys():
                        for timestamp in profile[k][sold_bought][dev][target].keys():
                            profile[k][sold_bought][dev][target][timestamp] = round_floats_for_ui(
                                profile[k][sold_bought][dev][target][timestamp])
        return profile
