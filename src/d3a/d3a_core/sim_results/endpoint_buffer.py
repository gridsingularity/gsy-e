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
import logging

from d3a_interface.constants_limits import ConstSettings, DATE_TIME_UI_FORMAT, GlobalConfig
from d3a_interface.results_validator import results_validator
from d3a_interface.sim_results.all_results import ResultsHandler
from d3a_interface.utils import get_json_dict_memory_allocation_size

from d3a.d3a_core.sim_results.offer_bids_trades_hr_stats import OfferBidTradeGraphStats
from d3a.d3a_core.util import get_market_maker_rate_from_config
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.finite_power_plant import FinitePowerPlant
from d3a.models.strategy.home_meter import HomeMeterStrategy
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.market_maker_strategy import MarketMakerStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.constants import FEED_IN_TARIFF

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

        self.bids_offers_trades = {}
        self.last_energy_trades_high_resolution = {}
        self.results_handler = ResultsHandler(should_export_plots)
        self.simulation_state = {"general": {}, "areas": {}}

        if ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR or \
                ConstSettings.GeneralSettings.EXPORT_ENERGY_TRADE_PROFILE_HR:
            self.offer_bid_trade_hr = OfferBidTradeGraphStats()

    def prepare_results_for_publish(self):
        result_report = self.generate_result_report()
        results_validator(result_report)

        message_size = get_json_dict_memory_allocation_size(result_report)
        if message_size > 64000:
            logging.error(f"Do not publish message bigger than 64 MB, current message size "
                          f"{message_size / 1000.0} MB.")
            return None
        logging.debug(f"Publishing {message_size} KB of data via Redis.")
        return result_report

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
            "status": self.status,
            "progress_info": self.simulation_progress,
            "simulation_state": self.simulation_state,
            **self.results_handler.all_raw_results
        }

    def _populate_core_stats_and_sim_state(self, area):
        if area.uuid not in self.flattened_area_core_stats_dict:
            self.flattened_area_core_stats_dict[area.uuid] = {}
        if self.current_market_time_slot_str == "":
            return
        core_stats_dict = {"bids": [], "offers": [], "trades": [], "market_fee": 0.0}
        if area.current_market is not None:
            for offer in area.current_market.offer_history:
                core_stats_dict["offers"].append(offer.serializable_dict())
            for bid in area.current_market.bid_history:
                core_stats_dict["bids"].append(bid.serializable_dict())
            for trade in area.current_market.trades:
                core_stats_dict["trades"].append(trade.serializable_dict())
            core_stats_dict["market_fee"] = area.current_market.market_fee
            core_stats_dict["const_fee_rate"] = (area.current_market.const_fee_rate
                                                 if area.current_market.const_fee_rate is not None
                                                 else 0.)
            core_stats_dict["feed_in_tariff"] = FEED_IN_TARIFF
            core_stats_dict["market_maker_rate"] = get_market_maker_rate_from_config(
                area.current_market)

        if area.strategy is None:
            core_stats_dict["area_throughput"] = {
                "baseline_peak_energy_import_kWh": area.throughput.baseline_peak_energy_import_kWh,
                "baseline_peak_energy_export_kWh": area.throughput.baseline_peak_energy_export_kWh,
                "import_capacity_kWh": area.throughput.import_capacity_kWh,
                "export_capacity_kWh": area.throughput.export_capacity_kWh,
                "imported_energy_kWh": area.stats.imported_traded_energy_kwh.get(
                    area.current_market.time_slot, 0.) if area.current_market is not None else 0.,
                "exported_energy_kWh": area.stats.exported_traded_energy_kwh.get(
                    area.current_market.time_slot, 0.) if area.current_market is not None else 0.,
            }
            core_stats_dict["grid_fee_constant"] = (area.current_market.const_fee_rate
                                                    if area.current_market is not None
                                                    else 0.)

        if isinstance(area.strategy, HomeMeterStrategy):
            core_stats_dict["home_meter_profile_kWh"] = (
                area.strategy.state.get_energy_at_market_slot(self.current_market_time_slot))
            if area.parent.current_market is not None:
                for trade in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict["trades"].append(trade.serializable_dict())

        elif isinstance(area.strategy, PVStrategy):
            core_stats_dict["pv_production_kWh"] = (
                area.strategy.state.get_energy_production_forecast_kWh(
                    self.current_market_time_slot, 0.0))
            core_stats_dict["available_energy_kWh"] = (
                area.strategy.state.get_available_energy_kWh(self.current_market_time_slot))
            if area.parent.current_market is not None:
                for trade in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict["trades"].append(trade.serializable_dict())

        elif isinstance(area.strategy, StorageStrategy):
            core_stats_dict["soc_history_%"] = (
                area.strategy.state.charge_history.get(self.current_market_time_slot, 0))
            if area.parent.current_market is not None:
                for trade in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict["trades"].append(trade.serializable_dict())

        elif isinstance(area.strategy, LoadHoursStrategy):
            core_stats_dict["load_profile_kWh"] = (
                area.strategy.state.get_desired_energy_Wh(self.current_market_time_slot) / 1000.0)
            core_stats_dict["total_energy_demanded_wh"] = (
                area.strategy.state.total_energy_demanded_Wh)
            core_stats_dict["energy_requirement_kWh"] = (
                area.strategy.state.get_energy_requirement_Wh(
                    self.current_market_time_slot) / 1000.0)

            if area.parent.current_market is not None:
                for trade in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict["trades"].append(trade.serializable_dict())

        elif type(area.strategy) == FinitePowerPlant:
            core_stats_dict["production_kWh"] = area.strategy.energy_per_slot_kWh
            if area.parent.current_market is not None:
                for trade in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict["trades"].append(trade.serializable_dict())

        elif type(area.strategy) in [InfiniteBusStrategy, MarketMakerStrategy, CommercialStrategy]:
            if area.parent.current_market is not None:
                core_stats_dict["energy_rate"] = (
                    area.strategy.energy_rate.get(area.parent.current_market.time_slot, None))
                for trade in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict["trades"].append(trade.serializable_dict())

        self.flattened_area_core_stats_dict[area.uuid] = core_stats_dict

        self.simulation_state["areas"][area.uuid] = area.get_state()

        for child in area.children:
            self._populate_core_stats_and_sim_state(child)

    def update_stats(self, area, simulation_status, progress_info, sim_state):
        self.area_result_dict = self._create_area_tree_dict(area)
        self.status = simulation_status
        is_initial_current_market_on_cn = GlobalConfig.IS_CANARY_NETWORK and \
            (area.next_market is None or (area.current_market and
             area.next_market.time_slot - area.current_market.time_slot > area.config.slot_length))
        if area.current_market is not None and not is_initial_current_market_on_cn:
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

        self.results_handler.update(
            self.area_result_dict, self.flattened_area_core_stats_dict,
            self.current_market_time_slot_str
        )

        self.bids_offers_trades.clear()

        if ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR or \
                ConstSettings.GeneralSettings.EXPORT_ENERGY_TRADE_PROFILE_HR:
            self.offer_bid_trade_hr.update(area)

        self.result_area_uuids = set()
        self.update_results_area_uuids(area)
        self.update_offer_bid_trade()

    def update_offer_bid_trade(self):
        if self.current_market_time_slot_str == "":
            return
        for area_uuid, area_result in self.flattened_area_core_stats_dict.items():
            self.bids_offers_trades[area_uuid] = \
                {k: area_result[k] for k in ('offers', 'bids', 'trades')}
