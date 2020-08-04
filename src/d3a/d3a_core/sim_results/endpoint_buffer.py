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
from d3a.d3a_core.sim_results.area_statistics import MarketPriceEnergyDay
from d3a.d3a_core.sim_results.area_throughput_stats import AreaThroughputStats
from d3a.d3a_core.sim_results.bills import MarketEnergyBills, CumulativeBills
from d3a.d3a_core.sim_results.device_statistics import DeviceStatistics
from d3a.d3a_core.sim_results.export_unmatched_loads import MarketUnmatchedLoads
from d3a_interface.constants_limits import ConstSettings
from d3a.d3a_core.sim_results.kpi import KPI
from d3a.d3a_core.sim_results.area_market_stock_stats import OfferBidTradeGraphStats
from d3a_interface.utils import convert_pendulum_to_str_in_dict
from d3a.d3a_core.sim_results.energy_trade_profile import EnergyTradeProfile
from d3a.d3a_core.sim_results.cumulative_grid_trades import CumulativeGridTrades

_NO_VALUE = {
    'min': None,
    'avg': None,
    'max': None
}


class SimulationEndpointBuffer:
    def __init__(self, job_id, initial_params, area, should_export_plots):
        self.job_id = job_id
        self.current_market = ""
        self.random_seed = initial_params["seed"] if initial_params["seed"] is not None else ''
        self.status = {}
        self.simulation_progress = {
            "eta_seconds": 0,
            "elapsed_time_seconds": 0,
            "percentage_completed": 0
        }
        self.should_export_plots = should_export_plots

        self.market_unmatched_loads = MarketUnmatchedLoads(area)
        self.price_energy_day = MarketPriceEnergyDay()
        self.market_bills = MarketEnergyBills()
        self.cumulative_bills = CumulativeBills()
        self.balancing_bills = MarketEnergyBills(is_spot_market=False)
        self.cumulative_grid_trades = CumulativeGridTrades()
        self.device_statistics = DeviceStatistics()
        self.trade_profile = EnergyTradeProfile(should_export_plots)
        self.kpi = KPI()
        self.area_throughput_stats = AreaThroughputStats()

        self.bids_offers_trades = {}
        self.last_energy_trades_high_resolution = {}

        if ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR:
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
                self.trade_profile.traded_energy_current, {}, ui_format=True),
            "last_price_energy_day": convert_pendulum_to_str_in_dict(
                self.price_energy_day.redis_output, {}),
            "last_device_statistics": convert_pendulum_to_str_in_dict(
                self.device_statistics.current_stats_dict, {}),
            "area_throughput": self.area_throughput_stats.results_redis,
            "last_energy_trades_high_resolution": convert_pendulum_to_str_in_dict(
                self.last_energy_trades_high_resolution, {}),
            "bids_offers_trades": self.bids_offers_trades
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

        self.market_unmatched_loads.update_unmatched_loads(area)

        self.device_statistics.update(area)

        self.price_energy_day.update(area)

        self.kpi.update_kpis_from_area(area)

        self.area_throughput_stats.update(area)

        self.generate_result_report()

        self.bids_offers_trades.clear()

        self.trade_profile.update(area)

        self.update_area_aggregated_stats(area)

        if ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR:
            self.area_market_stocks_stats.update(area)

    def update_area_aggregated_stats(self, area):
        self._update_bids_offer_trades(area)
        self._merge_cumulative_bills_into_bills_for_market_info(area)
        for child in area.children:
            self.update_area_aggregated_stats(child)

    def _update_bids_offer_trades(self, area):
        if area.current_market is not None:
            self.bids_offers_trades[area.uuid] = area.current_market.get_bids_offers_trades()
            # TODO: (D3ASIM-2670) Trades are already stored in bids_offers_trades:
            #  accumulation of area.stats.market_trades endpoint should be deprecated
            self.last_energy_trades_high_resolution[area.uuid] = area.stats.market_trades

    def _merge_cumulative_bills_into_bills_for_market_info(self, area):
        # this is only needed for areas with external connection
        if area.redis_ext_conn:
            bills = self.market_bills.bills_redis_results[area.uuid]
            bills.update({
                "penalty_cost":
                    self.cumulative_bills.cumulative_bills_results[area.uuid]["penalties"],
                "penalty_energy":
                    self.cumulative_bills.cumulative_bills_results[area.uuid]["penalty_energy"]})
            area.stats.update_aggregated_stats({"bills": bills})

            area.stats.kpi.update(self.kpi.performance_indices_redis.get(area.uuid, None))
