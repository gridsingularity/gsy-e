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
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.predefined_pv import PVUserProfileStrategy, PVPredefinedStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.finite_power_plant import FinitePowerPlant
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.strategy.market_maker_strategy import MarketMakerStrategy

_NO_VALUE = {
    'min': None,
    'avg': None,
    'max': None
}


class SimulationEndpointBuffer:
    def __init__(self, job_id, initial_params, area, should_export_plots):
        self.job_id = job_id
        self.result_area_uuids = set()
        self.current_market = ""
        self.current_market_unix = None
        self.current_market_datetime = None
        self.random_seed = initial_params["seed"] if initial_params["seed"] is not None else ''
        self.status = {}
        self.area_result_dict = self._create_area_tree_dict(area)
        self.flattened_area_core_stats_dict = {}
        self.simulation_progress = {
            "eta_seconds": 0,
            "elapsed_time_seconds": 0,
            "percentage_completed": 0
        }
        self.should_export_plots = should_export_plots
        self.market_unmatched_loads = MarketUnmatchedLoads(area)
        self.price_energy_day = MarketPriceEnergyDay(should_export_plots)
        self.market_bills = MarketEnergyBills()
        self.cumulative_bills = CumulativeBills()
        if ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
            self.balancing_bills = MarketEnergyBills(is_spot_market=False)
        self.cumulative_grid_trades = CumulativeGridTrades()
        self.device_statistics = DeviceStatistics(should_export_plots)
        self.trade_profile = EnergyTradeProfile(should_export_plots)
        self.kpi = KPI(should_export_plots)
        self.area_throughput_stats = AreaThroughputStats()

        self.bids_offers_trades = {}
        self.last_energy_trades_high_resolution = {}

        if ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR or \
                ConstSettings.GeneralSettings.EXPORT_ENERGY_TRADE_PROFILE_HR:
            self.area_market_stocks_stats = OfferBidTradeGraphStats()

    @staticmethod
    def _structure_results_from_area_object(target_area):
        area_dict = dict()
        area_dict['name'] = target_area.name
        area_dict['uuid'] = target_area.uuid
        area_dict['type'] = str(target_area.strategy.__class__.__name__) \
            if target_area.strategy is not None else "Area"
        area_dict['children'] = []
        return area_dict

    def _create_area_tree_dict(self, area):
        area_result_dict = self._structure_results_from_area_object(area)
        for child in area.children:
            area_result_dict["children"].append(
                self._create_area_tree_dict(child)
            )
        return area_result_dict

    def update_results_area_uuids(self, area):
        if area.strategy is not None or (area.strategy is None and area.children):
            self.result_area_uuids.update({area.uuid})
        for child in area.children:
            self.update_results_area_uuids(child)

    def generate_result_report(self):
        # TODO: In D3ASIM-2288, add unix_time=True to convert_pendulum_to_str_in_dict
        return {
            "job_id": self.job_id,
            "current_market": self.current_market,
            "random_seed": self.random_seed,
            "cumulative_grid_trades": self.cumulative_grid_trades.current_trades,
            "bills": self.market_bills.bills_redis_results,
            "cumulative_bills": self.cumulative_bills.cumulative_bills,
            "status": self.status,
            "progress_info": self.simulation_progress,
            "kpi": self.kpi.performance_indices_redis,
            "last_unmatched_loads": self.market_unmatched_loads.last_unmatched_loads,
            "last_energy_trade_profile": convert_pendulum_to_str_in_dict(
                self.trade_profile.traded_energy_current, {}, ui_format=True),
            "last_price_energy_day": convert_pendulum_to_str_in_dict(
                self.price_energy_day.redis_output, {}),
            "last_device_statistics": self.device_statistics.current_stats_dict,
            "area_throughput": self.area_throughput_stats.results_redis,
            "last_energy_trades_high_resolution": convert_pendulum_to_str_in_dict(
                self.last_energy_trades_high_resolution, {}),
            "bids_offers_trades": self.bids_offers_trades,
            "results_area_uuids": list(self.result_area_uuids),
        }

    def generate_json_report(self):
        return {
            "job_id": self.job_id,
            "random_seed": self.random_seed,
            "unmatched_loads": self.market_unmatched_loads.unmatched_loads,
            "price_energy_day": convert_pendulum_to_str_in_dict(
                self.price_energy_day.csv_output, {}),
            "cumulative_grid_trades":
                self.cumulative_grid_trades.current_trades,
            "bills": self.market_bills.bills_results,
            "cumulative_bills": self.cumulative_bills.cumulative_bills,
            "status": self.status,
            "progress_info": self.simulation_progress,
            "device_statistics": self.device_statistics.device_stats_dict,
            "energy_trade_profile": convert_pendulum_to_str_in_dict(
                self.trade_profile.traded_energy_profile, {}, ui_format=True),
            "kpi": self.kpi.performance_indices,
            "area_throughput": self.area_throughput_stats.results,
        }

    def _populate_core_stats(self, area):
        if area.uuid not in self.flattened_area_core_stats_dict:
            self.flattened_area_core_stats_dict[area.uuid] = {}
        if self.current_market == "":
            return
        core_stats_dict = {'bids': [], 'offers': [], 'trades': []}
        if hasattr(area.current_market, 'offer_history'):
            for offer in area.current_market.offer_history:
                core_stats_dict['offers'].append(offer.serializable_dict())
        if hasattr(area.current_market, 'bid_history'):
            for bid in area.current_market.bid_history:
                core_stats_dict['bids'].append(bid.serializable_dict())
        if hasattr(area.current_market, 'trades'):
            for trade in area.current_market.trades:
                core_stats_dict['trades'].append(trade.serializable_dict())

        if isinstance(area.strategy, PVStrategy) or \
                isinstance(area.strategy, PVUserProfileStrategy) or \
                isinstance(area.strategy, PVPredefinedStrategy):
            core_stats_dict['pv_production_kWh'] = \
                area.strategy.energy_production_forecast_kWh.get(self.current_market_datetime,
                                                                 0)
            if area.parent.current_market is not None:
                for t in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict['trades'].append(t.serializable_dict())

        elif isinstance(area.strategy, StorageStrategy):
            core_stats_dict['soc_history_%'] = \
                area.strategy.state.charge_history.get(self.current_market_datetime, 0)
            if area.parent.current_market is not None:
                for t in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict['trades'].append(t.serializable_dict())

        elif isinstance(area.strategy, LoadHoursStrategy):
            core_stats_dict['load_profile_kWh'] = \
                area.strategy.state.desired_energy_Wh.get(self.current_market_datetime, 0)
            if area.parent.current_market is not None:
                for t in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict['trades'].append(t.serializable_dict())

        elif type(area.strategy) == FinitePowerPlant:
            core_stats_dict['production_kWh'] = area.strategy.energy_per_slot_kWh
            if area.parent.current_market is not None:
                for t in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict['trades'].append(t.serializable_dict())

        elif type(area.strategy) in [InfiniteBusStrategy, MarketMakerStrategy]:
            if area.parent.current_market is not None:
                for t in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict['trades'].append(t.serializable_dict())

        self.flattened_area_core_stats_dict[area.uuid] = core_stats_dict

        for child in area.children:
            self._populate_core_stats(child)

    def update_stats(self, area, simulation_status, progress_info):
        self.status = simulation_status
        if area.current_market is not None:
            self.current_market = area.current_market.time_slot_str
            self.current_market_unix = area.current_market.time_slot.timestamp()
            self.current_market_datetime = area.current_market.time_slot
        self._populate_core_stats(area)
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

        self.market_unmatched_loads.update_unmatched_loads(
            self.area_result_dict, self.flattened_area_core_stats_dict, self.current_market
        )

        self.device_statistics.update(self.area_result_dict,
                                      self.flattened_area_core_stats_dict,
                                      self.current_market)

        self.price_energy_day.update(area)

        self.kpi.update_kpis_from_area(area)

        self.area_throughput_stats.update(area)

        self.generate_result_report()

        self.bids_offers_trades.clear()

        self.trade_profile.update(area)

        self.update_area_aggregated_stats(area)

        if ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR or \
                ConstSettings.GeneralSettings.EXPORT_ENERGY_TRADE_PROFILE_HR:
            self.area_market_stocks_stats.update(area)

        self.result_area_uuids = set()
        self.update_results_area_uuids(area)
        self.update_offer_bid_trade()

    def update_area_aggregated_stats(self, area):
        self._merge_cumulative_bills_into_bills_for_market_info(area)
        for child in area.children:
            self.update_area_aggregated_stats(child)

    def update_offer_bid_trade(self):
        if self.current_market == "":
            return
        for area_uuid, area_result in self.flattened_area_core_stats_dict.items():
            self.bids_offers_trades[area_uuid] = area_result

    def _merge_cumulative_bills_into_bills_for_market_info(self, area):
        bills = self.market_bills.bills_redis_results[area.uuid]
        bills.update({
            "penalty_cost":
                self.cumulative_bills.cumulative_bills_results[area.uuid]["penalties"],
            "penalty_energy":
                self.cumulative_bills.cumulative_bills_results[area.uuid]["penalty_energy"]})
        area.stats.update_aggregated_stats({"bills": bills})

        area.stats.kpi.update(self.kpi.performance_indices_redis.get(area.uuid, {}))
