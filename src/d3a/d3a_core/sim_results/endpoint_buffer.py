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
    export_cumulative_grid_trades_redis, MarketPriceEnergyDay, \
    generate_inter_area_trade_details
from d3a.d3a_core.sim_results.area_throughput_stats import AreaThroughputStats
from d3a.d3a_core.sim_results.file_export_endpoints import FileExportEndpoints
from d3a.d3a_core.sim_results.stats import MarketEnergyBills, CumulativeBills
from d3a.d3a_core.sim_results.device_statistics import DeviceStatistics
from d3a.d3a_core.sim_results.export_unmatched_loads import MarketUnmatchedLoads
from d3a_interface.constants_limits import ConstSettings
from d3a.d3a_core.sim_results.kpi import KPI
from d3a.d3a_core.sim_results.area_market_stock_stats import OfferBidTradeGraphStats
from d3a.d3a_core.util import convert_pendulum_to_str_in_dict

_NO_VALUE = {
    'min': None,
    'avg': None,
    'max': None
}


class SimulationEndpointBuffer:
    def __init__(self, job_id, initial_params, area, export_plots=True):
        self.job_id = job_id
        self.current_market = ""
        self.random_seed = initial_params["seed"] if initial_params["seed"] is not None else ''
        self.status = {}
        self.simulation_progress = {
            "eta_seconds": 0,
            "elapsed_time_seconds": 0,
            "percentage_completed": 0
        }
        self.market_unmatched_loads = MarketUnmatchedLoads(area)
        self.price_energy_day = MarketPriceEnergyDay()
        self.market_bills = MarketEnergyBills()
        self.cumulative_bills = CumulativeBills()
        self.balancing_bills = MarketEnergyBills(is_spot_market=False)
        self.cumulative_grid_trades = CumulativeGridTrades()
        self.trade_details = {}
        self.device_statistics = DeviceStatistics()
        self.file_export_endpoints = FileExportEndpoints(export_plots)
        self.kpi = KPI()
        self.area_throughput_stats = AreaThroughputStats()

        self.last_unmatched_loads = {}
        self.export_plots = export_plots
        if export_plots:
            self.area_market_stocks_stats = OfferBidTradeGraphStats()

    def generate_result_report(self):
        # TODO: In D3ASIM-2288, add unix_time=True to convert_pendulum_to_str_in_dict
        return {
            "job_id": self.job_id,
            "current_market": self.current_market,
            "random_seed": self.random_seed,
            "cumulative_grid_trades": self.cumulative_grid_trades.current_trades_redis,
            "bills": self.market_bills.bills_redis_results,
            "cumulative_bills": self.cumulative_bills.cumulative_bills,
            "status": self.status,
            "progress_info": self.simulation_progress,
            "kpi": self.kpi.performance_indices_redis,
            "last_unmatched_loads": convert_pendulum_to_str_in_dict(
                self.market_unmatched_loads.last_unmatched_loads, {}),
            "last_energy_trade_profile": convert_pendulum_to_str_in_dict(
                self.file_export_endpoints.traded_energy_current, {}, ui_format=True),
            "last_price_energy_day": convert_pendulum_to_str_in_dict(
                self.price_energy_day.redis_output, {}),
            "last_device_statistics": convert_pendulum_to_str_in_dict(
                self.device_statistics.current_stats_dict, {}),
            "area_throughput": self.area_throughput_stats.results_redis
        }

    def generate_json_report(self):
        return {
            "job_id": self.job_id,
            "random_seed": self.random_seed,
            "unmatched_loads": convert_pendulum_to_str_in_dict(
                self.market_unmatched_loads.unmatched_loads, {}),
            "price_energy_day": convert_pendulum_to_str_in_dict(
                self.price_energy_day.csv_output, {}),
            "cumulative_grid_trades": self.cumulative_grid_trades.current_trades_redis,
            "bills": self.market_bills.bills_results,
            "cumulative_bills": self.cumulative_bills.cumulative_bills,
            "status": self.status,
            "progress_info": self.simulation_progress,
            "device_statistics": convert_pendulum_to_str_in_dict(
                self.device_statistics.device_stats_dict, {}),
            "energy_trade_profile": convert_pendulum_to_str_in_dict(
                self.file_export_endpoints.traded_energy_profile, {}, ui_format=True),
            "kpi": self.kpi.performance_indices,
            "area_throughput": self.area_throughput_stats.results
        }

    def update_stats(self, area, simulation_status, progress_info):
        self.status = simulation_status
        if area.current_market is not None:
            self.current_market = area.current_market.time_slot_str
        self.simulation_progress = {
            "eta_seconds": progress_info.eta.seconds,
            "elapsed_time_seconds": progress_info.elapsed_time.seconds,
            "percentage_completed": int(progress_info.percentage_completed)
        }

        self.cumulative_grid_trades.update(area)

        self.market_bills.update(area)
        if ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
            self.balancing_bills.update(area)

        self.cumulative_bills.update_cumulative_bills(area)

        self.trade_details = generate_inter_area_trade_details(area, "past_markets")

        self.file_export_endpoints(area)
        self.market_unmatched_loads.update_unmatched_loads(area)
        self.device_statistics.update(area)

        self.price_energy_day.update(area)

        self.kpi.update_kpis_from_area(area)

        self.area_throughput_stats.update(area)

        self.generate_result_report()

        self.update_area_aggregated_stats(area)

        if self.export_plots:
            self.area_market_stocks_stats.update(area)

    def _send_results_to_areas(self, area):
        stats = {
            "kpi": self.kpi.performance_indices_redis.get(area.uuid, None)
        }
        area.endpoint_stats.update(stats)

    def update_area_aggregated_stats(self, area):
        self._update_area_stats(area)
        self._send_results_to_areas(area)
        for child in area.children:
            self.update_area_aggregated_stats(child)

    def _update_area_stats(self, area):
        bills = self.market_bills.bills_redis_results[area.uuid]
        bills.update({
            "penalty_cost": self.cumulative_bills.cumulative_bills_results[area.uuid]["penalties"],
            "penalty_energy":
                self.cumulative_bills.cumulative_bills_results[area.uuid]["penalty_energy"]})
        area.stats.update_aggregated_stats({"bills": bills})


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
