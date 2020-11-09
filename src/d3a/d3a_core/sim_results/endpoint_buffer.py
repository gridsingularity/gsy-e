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

from d3a_interface.sim_results.market_price_energy_day import MarketPriceEnergyDay
from d3a_interface.sim_results.area_throughput_stats import AreaThroughputStats
from d3a_interface.sim_results.bills import MarketEnergyBills, CumulativeBills
from d3a_interface.sim_results.device_statistics import DeviceStatistics
from d3a_interface.sim_results.export_unmatched_loads import MarketUnmatchedLoads
from d3a_interface.constants_limits import ConstSettings, DATE_TIME_UI_FORMAT
from d3a_interface.sim_results.kpi import KPI
from d3a.d3a_core.sim_results.area_market_stock_stats import OfferBidTradeGraphStats
from d3a_interface.utils import convert_pendulum_to_str_in_dict
from d3a_interface.sim_results.energy_trade_profile import EnergyTradeProfile
from d3a_interface.sim_results.cumulative_grid_trades import CumulativeGridTrades
from d3a.models.strategy.pv import PVStrategy
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
        self.current_market_time_slot_str = ""
        self.current_market_ui_time_slot_str = ""
        self.current_market_time_slot_unix = None
        self.current_market_time_slot = None
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
        self.market_bills = MarketEnergyBills()
        self.kpi = KPI(should_export_plots)
        if self.should_export_plots:
            self.market_unmatched_loads = MarketUnmatchedLoads()
            self.price_energy_day = MarketPriceEnergyDay(should_export_plots)
            self.cumulative_bills = CumulativeBills()
            if ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
                self.balancing_bills = MarketEnergyBills(is_spot_market=False)
            self.cumulative_grid_trades = CumulativeGridTrades()
            self.device_statistics = DeviceStatistics(should_export_plots)
            self.trade_profile = EnergyTradeProfile(should_export_plots)
            self.area_throughput_stats = AreaThroughputStats()

        self.bids_offers_trades = {}
        self.last_energy_trades_high_resolution = {}

        self.simulation_state = {"general": {}, "areas": {}}

        if ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR or \
                ConstSettings.GeneralSettings.EXPORT_ENERGY_TRADE_PROFILE_HR:
            self.area_market_stocks_stats = OfferBidTradeGraphStats()

    @staticmethod
    def _structure_results_from_area_object(target_area):
        area_dict = dict()
        area_dict['name'] = target_area.name
        area_dict['uuid'] = target_area.uuid
        area_dict['parent_uuid'] = target_area.parent.uuid \
            if target_area.parent is not None else ""
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
            "current_market": self.current_market_time_slot_str,
            "current_market_ui_time_slot_str": self.current_market_ui_time_slot_str,
            "random_seed": self.random_seed,
            "status": self.status,
            "progress_info": self.simulation_progress,
            "bids_offers_trades": self.bids_offers_trades,
            "results_area_uuids": list(self.result_area_uuids),
            "simulation_state": self.simulation_state,
            "simulation_raw_data": self.flattened_area_core_stats_dict,
            "configuration_tree": self.area_result_dict
        }

    def generate_json_report(self):
        return {
            "job_id": self.job_id,
            "random_seed": self.random_seed,
            "unmatched_loads": self.market_unmatched_loads.unmatched_loads,
            "price_energy_day": self.price_energy_day.csv_output,
            "cumulative_grid_trades":
                self.cumulative_grid_trades.current_trades,
            "bills": self.market_bills.bills_results,
            "cumulative_bills": self.cumulative_bills.cumulative_bills,
            "cumulative_market_fees": self.market_bills.cumulative_fee_charged_per_market,
            "status": self.status,
            "progress_info": self.simulation_progress,
            "device_statistics": self.device_statistics.device_stats_dict,
            "energy_trade_profile": convert_pendulum_to_str_in_dict(
                self.trade_profile.traded_energy_profile, {}, ui_format=True),
            "kpi": self.kpi.performance_indices,
            "area_throughput": self.area_throughput_stats.results,
            "simulation_state": self.simulation_state
        }

    def _populate_core_stats_and_sim_state(self, area):
        if area.uuid not in self.flattened_area_core_stats_dict:
            self.flattened_area_core_stats_dict[area.uuid] = {}
        if self.current_market_time_slot_str == "":
            return
        core_stats_dict = {'bids': [], 'offers': [], 'trades': [], 'market_fee': 0.0}
        if hasattr(area.current_market, 'offer_history'):
            for offer in area.current_market.offer_history:
                core_stats_dict['offers'].append(offer.serializable_dict())
        if hasattr(area.current_market, 'bid_history'):
            for bid in area.current_market.bid_history:
                core_stats_dict['bids'].append(bid.serializable_dict())
        if hasattr(area.current_market, 'trades'):
            for trade in area.current_market.trades:
                core_stats_dict['trades'].append(trade.serializable_dict())
        if hasattr(area.current_market, 'market_fee'):
            core_stats_dict['market_fee'] = area.current_market.market_fee
        if area.strategy is None:
            core_stats_dict['area_throughput'] = {
                'baseline_peak_energy_import_kWh': area.baseline_peak_energy_import_kWh,
                'baseline_peak_energy_export_kWh': area.baseline_peak_energy_export_kWh,
                'import_capacity_kWh': area.import_capacity_kWh,
                'export_capacity_kWh': area.export_capacity_kWh,
                'imported_energy_kWh': area.stats.imported_energy.get(
                    area.current_market.time_slot, 0.) if area.current_market is not None else 0.,
                'exported_energy_kWh': area.stats.exported_energy.get(
                    area.current_market.time_slot, 0.) if area.current_market is not None else 0.,
                'net_energy_flow_kWh': area.stats.net_energy_flow.get(
                    area.current_market.time_slot, 0.) if area.current_market is not None else 0.
            }
            core_stats_dict['grid_fee_constant'] = area.current_market.const_fee_rate \
                if area.current_market is not None else 0.

        if isinstance(area.strategy, PVStrategy):
            core_stats_dict['pv_production_kWh'] = \
                area.strategy.energy_production_forecast_kWh.get(self.current_market_time_slot,
                                                                 0)
            core_stats_dict['available_energy_kWh'] = \
                area.strategy.state.available_energy_kWh.get(self.current_market_time_slot, 0)
            if area.parent.current_market is not None:
                for t in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict['trades'].append(t.serializable_dict())

        elif isinstance(area.strategy, StorageStrategy):
            core_stats_dict['soc_history_%'] = \
                area.strategy.state.charge_history.get(self.current_market_time_slot, 0)
            if area.parent.current_market is not None:
                for t in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict['trades'].append(t.serializable_dict())

        elif isinstance(area.strategy, LoadHoursStrategy):
            core_stats_dict['load_profile_kWh'] = \
                area.strategy.state.desired_energy_Wh.get(
                    self.current_market_time_slot, 0) / 1000.0
            core_stats_dict['total_energy_demanded_wh'] = \
                area.strategy.state.total_energy_demanded_wh
            core_stats_dict['energy_requirement_kWh'] = \
                area.strategy.energy_requirement_Wh.get(
                    self.current_market_time_slot, 0) / 1000.0

            if area.parent.current_market is not None:
                for t in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict['trades'].append(t.serializable_dict())

        elif type(area.strategy) == FinitePowerPlant:
            core_stats_dict['production_kWh'] = area.strategy.energy_per_slot_kWh
            if area.parent.current_market is not None:
                for t in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict['trades'].append(t.serializable_dict())

        elif type(area.strategy) in [InfiniteBusStrategy, MarketMakerStrategy]:
            core_stats_dict['energy_rate'] = \
                area.strategy.energy_rate[area.parent.current_market.time_slot]
            if area.parent.current_market is not None:
                for t in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict['trades'].append(t.serializable_dict())

        self.flattened_area_core_stats_dict[area.uuid] = core_stats_dict

        self.simulation_state["areas"][area.uuid] = area.get_state()

        for child in area.children:
            self._populate_core_stats_and_sim_state(child)

    def update_stats(self, area, simulation_status, progress_info, sim_state):
        self.area_result_dict = self._create_area_tree_dict(area)
        self.status = simulation_status
        if area.current_market is not None:
            self.current_market_time_slot_str = area.current_market.time_slot_str
            self.current_market_ui_time_slot_str = \
                area.current_market.time_slot.format(DATE_TIME_UI_FORMAT)
            self.current_market_time_slot_unix = area.current_market.time_slot.timestamp()
            self.current_market_time_slot = area.current_market.time_slot
        self.simulation_state["general"] = sim_state
        self._populate_core_stats_and_sim_state(area)
        self.simulation_progress = {
            "eta_seconds": progress_info.eta.seconds if progress_info.eta else None,
            "elapsed_time_seconds": progress_info.elapsed_time.seconds,
            "percentage_completed": int(progress_info.percentage_completed)
        }
        if self.current_market_time_slot_str != "":
            self.market_bills.update(self.area_result_dict, self.flattened_area_core_stats_dict)

        self.kpi.update_kpis_from_area(self.area_result_dict,
                                       self.flattened_area_core_stats_dict,
                                       self.current_market_time_slot_str)
        if self.should_export_plots:
            self.cumulative_grid_trades.update(self.area_result_dict,
                                               self.flattened_area_core_stats_dict)

            self.cumulative_bills.update_cumulative_bills(self.area_result_dict,
                                                          self.flattened_area_core_stats_dict,
                                                          self.current_market_time_slot_str)

            self.market_unmatched_loads.update_unmatched_loads(
                self.area_result_dict, self.flattened_area_core_stats_dict,
                self.current_market_time_slot_str
            )

            self.device_statistics.update(self.area_result_dict,
                                          self.flattened_area_core_stats_dict,
                                          self.current_market_time_slot_str)

            self.price_energy_day.update(self.area_result_dict,
                                         self.flattened_area_core_stats_dict,
                                         self.current_market_time_slot_str)

            self.trade_profile.update(
                self.area_result_dict,
                self.flattened_area_core_stats_dict,
                self.current_market_ui_time_slot_str
            )

            self.area_throughput_stats.update(self.area_result_dict,
                                              self.flattened_area_core_stats_dict,
                                              self.current_market_time_slot_str)

        self.generate_result_report()

        self.bids_offers_trades.clear()

        if ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR or \
                ConstSettings.GeneralSettings.EXPORT_ENERGY_TRADE_PROFILE_HR:
            self.area_market_stocks_stats.update(area)

        self.result_area_uuids = set()
        self.update_results_area_uuids(area)
        self.update_offer_bid_trade()

    def update_area_aggregated_stats(self, area_dict):
        self._merge_cumulative_bills_into_bills_for_market_info(area_dict)
        for child in area_dict['children']:
            self.update_area_aggregated_stats(child)

    def update_offer_bid_trade(self):
        if self.current_market_time_slot_str == "":
            return
        for area_uuid, area_result in self.flattened_area_core_stats_dict.items():
            self.bids_offers_trades[area_uuid] = \
                {k: area_result[k] for k in ('offers', 'bids', 'trades')}

    def _merge_cumulative_bills_into_bills_for_market_info(self, area_dict):
        bills = self.market_bills.bills_redis_results[area_dict['uuid']]
        bills.update({
            "penalty_cost":
                self.cumulative_bills.cumulative_bills_results[area_dict['uuid']]["penalties"],
            "penalty_energy":
                self.cumulative_bills.cumulative_bills_results[area_dict['uuid']]["penalty_energy"]
        })
