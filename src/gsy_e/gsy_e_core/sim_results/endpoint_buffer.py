"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
from typing import TYPE_CHECKING, Dict, List

from gsy_framework.constants_limits import (DATE_TIME_FORMAT, DATE_TIME_UI_FORMAT, ConstSettings,
                                            GlobalConfig)
from gsy_framework.results_validator import results_validator
from gsy_framework.sim_results.all_results import ResultsHandler
from gsy_framework.utils import get_json_dict_memory_allocation_size
from pendulum import DateTime

from gsy_e.gsy_e_core.sim_results.offer_bids_trades_hr_stats import OfferBidTradeGraphStats
from gsy_e.gsy_e_core.util import (get_feed_in_tariff_rate_from_config,
                                   get_market_maker_rate_from_config)
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.finite_power_plant import FinitePowerPlant

if TYPE_CHECKING:
    from gsy_e.gsy_e_core.simulation import SimulationProgressInfo
    from gsy_e.models.area import Area, AreaBase
    from gsy_e.models.area.scm_manager import SCMManager
    from gsy_e.models.market import MarketBase

_NO_VALUE = {
    "min": None,
    "avg": None,
    "max": None
}


# pylint: disable=too-many-instance-attributes
# pylint: disable=logging-too-many-args
class SimulationEndpointBuffer:
    """Handles collecting and buffering of all results for all areas."""

    def __init__(self, job_id, random_seed, area, should_export_plots):
        self.job_id = job_id
        self.result_area_uuids = set()
        self.current_market_time_slot_str = ""
        self.current_market_ui_time_slot_str = ""
        self.current_market_time_slot_unix = None
        self.current_market_time_slot = None
        self.random_seed = random_seed if random_seed is not None else ""
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

        if (ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR or
                ConstSettings.GeneralSettings.EXPORT_ENERGY_TRADE_PROFILE_HR):
            self.offer_bid_trade_hr = OfferBidTradeGraphStats()

    def prepare_results_for_publish(self) -> Dict:
        """Validate, serialise and check size of the results before sending to gsy-web."""
        result_report = self.generate_result_report()
        results_validator(result_report)

        message_size = get_json_dict_memory_allocation_size(result_report)
        if message_size > 64000:
            logging.error("Do not publish message bigger than 64 MB, "
                          "current message size %s MB.", (message_size / 1000.0))
            return {}
        logging.debug("Publishing %s KB of data via Redis.", message_size)
        return result_report

    @staticmethod
    def _structure_results_from_area_object(target_area: "AreaBase") -> Dict:
        """Add basic information about the area in the area_tree_dict."""
        area_dict = {}
        area_dict["name"] = target_area.name
        area_dict["uuid"] = target_area.uuid
        area_dict["parent_uuid"] = (target_area.parent.uuid
                                    if target_area.parent is not None else "")
        area_dict["type"] = (str(target_area.strategy.__class__.__name__)
                             if target_area.strategy is not None else "Area")
        area_dict["children"] = []
        return area_dict

    def _create_area_tree_dict(self, area: "AreaBase") -> Dict:
        """Create a tree that mirrors the setup architecture and contains basic information."""
        area_result_dict = self._structure_results_from_area_object(area)
        for child in area.children:
            area_result_dict["children"].append(
                self._create_area_tree_dict(child)
            )
        return area_result_dict

    def update_results_area_uuids(self, area: "AreaBase") -> None:
        """Populate a set of area uuids that contribute to the stats."""
        if area.strategy is not None or (area.strategy is None and area.children):
            self.result_area_uuids.update({area.uuid})
        for child in area.children:
            self.update_results_area_uuids(child)

    def generate_result_report(self) -> Dict:
        """Create dict that contains all statistics that are sent to the gsy-web."""
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

    def generate_json_report(self) -> Dict:
        """Create dict that contains all locally exported statistics (for JSON files)."""
        return {
            "job_id": self.job_id,
            "random_seed": self.random_seed,
            "status": self.status,
            "progress_info": self.simulation_progress,
            "simulation_state": self.simulation_state,
            **self.results_handler.all_raw_results
        }

    def _read_settlement_markets_stats_to_dict(self, area: "Area") -> Dict[str, Dict]:
        """Read last settlement market and return market_stats in a dict."""
        stats_dict = {}
        if not area.last_past_settlement_market:
            return stats_dict
        last_market_time = area.last_past_settlement_market[0].format(DATE_TIME_FORMAT)
        last_market_obj = area.last_past_settlement_market[1]
        stats_dict[last_market_time] = self._read_market_stats_to_dict(last_market_obj)
        return stats_dict

    @staticmethod
    def _get_future_orders_from_timeslot(future_orders: List, time_slot: DateTime) -> List:
        return [order.serializable_dict()
                for order in future_orders
                if order.time_slot == time_slot]

    def _read_future_markets_stats_to_dict(self, area: "Area") -> Dict[str, Dict]:
        """Read future markets and return market_stats in a dict."""

        stats_dict = {}
        if not area.future_markets:
            return stats_dict

        for time_slot in area.future_market_time_slots:
            time_slot_str = time_slot.format(DATE_TIME_FORMAT)
            stats_dict[time_slot_str] = {
                "bids": self._get_future_orders_from_timeslot(
                    area.future_markets.bid_history, time_slot),
                "offers": self._get_future_orders_from_timeslot(
                    area.future_markets.offer_history, time_slot),
                "trades": self._get_future_orders_from_timeslot(
                    area.future_markets.trades, time_slot),
                "market_fee": area.future_markets.market_fee,
                "const_fee_rate": (area.future_markets.const_fee_rate
                                   if area.future_markets.const_fee_rate is not None else 0.),
                "feed_in_tariff": get_feed_in_tariff_rate_from_config(area.future_markets,
                                                                      time_slot=time_slot),
                "market_maker_rate": get_market_maker_rate_from_config(
                    area.future_markets, time_slot=time_slot)
            }

        return stats_dict

    @staticmethod
    def _read_market_stats_to_dict(market: "MarketBase") -> Dict:
        """Read all market related stats to a dictionary."""
        stats_dict = {"bids": [], "offers": [], "trades": [], "market_fee": 0.0}
        for offer in market.offer_history:
            stats_dict["offers"].append(offer.serializable_dict())
        for bid in market.bid_history:
            stats_dict["bids"].append(bid.serializable_dict())
        for trade in market.trades:
            stats_dict["trades"].append(trade.serializable_dict())

        stats_dict["market_fee"] = market.market_fee
        stats_dict["const_fee_rate"] = (market.const_fee_rate
                                        if market.const_fee_rate is not None else 0.)
        stats_dict["feed_in_tariff"] = get_feed_in_tariff_rate_from_config(market)
        stats_dict["market_maker_rate"] = get_market_maker_rate_from_config(market)
        return stats_dict

    # pylint: disable=too-many-branches
    def _populate_core_stats_and_sim_state(self, area: "Area") -> None:
        """Populate all area statistics and state into self.flattened_area_core_stats_dict and
        self.simulation_state."""
        if area.uuid not in self.flattened_area_core_stats_dict:
            self.flattened_area_core_stats_dict[area.uuid] = {}
        if self.current_market_time_slot_str == "":
            return
        core_stats_dict = {"bids": [], "offers": [], "trades": [], "market_fee": 0.0}

        if area.current_market:
            core_stats_dict.update(self._read_market_stats_to_dict(area.current_market))

            if ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS:
                core_stats_dict["settlement_market_stats"] = (
                    self._read_settlement_markets_stats_to_dict(area))
            if ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS > 0:
                core_stats_dict["future_market_stats"] = (
                    self._read_future_markets_stats_to_dict(area)
                )

        if isinstance(area.strategy, CommercialStrategy):
            if isinstance(area.strategy, FinitePowerPlant):
                core_stats_dict["production_kWh"] = area.strategy.energy_per_slot_kWh
                if area.parent.current_market is not None:
                    for trade in area.strategy.trades[area.parent.current_market]:
                        core_stats_dict["trades"].append(trade.serializable_dict())
            else:
                if area.parent.current_market is not None:
                    core_stats_dict["energy_rate"] = (
                        area.strategy.energy_rate.get(area.parent.current_market.time_slot, None))
                    for trade in area.strategy.trades[area.parent.current_market]:
                        core_stats_dict["trades"].append(trade.serializable_dict())
        else:
            core_stats_dict.update(area.get_results_dict())
            if area.parent and area.parent.current_market and area.strategy:
                for trade in area.strategy.trades[area.parent.current_market]:
                    core_stats_dict["trades"].append(trade.serializable_dict())

        self.flattened_area_core_stats_dict[area.uuid] = core_stats_dict

        self.simulation_state["areas"][area.uuid] = area.get_state()

        for child in area.children:
            self._populate_core_stats_and_sim_state(child)

    def _calculate_and_update_last_market_time_slot(self, area: "Area"):
        is_initial_current_market_on_cn = (
                GlobalConfig.IS_CANARY_NETWORK and
                (area.spot_market is None or
                 (area.current_market and
                  area.spot_market.time_slot -
                  area.current_market.time_slot > area.config.slot_length)))
        if area.current_market is not None and not is_initial_current_market_on_cn:
            self.current_market_time_slot_str = area.current_market.time_slot_str
            self.current_market_ui_time_slot_str = (
                area.current_market.time_slot.format(DATE_TIME_UI_FORMAT))
            self.current_market_time_slot_unix = area.current_market.time_slot.timestamp()
            self.current_market_time_slot = area.current_market.time_slot

    def update_stats(self, area: "AreaBase", simulation_status: str,
                     progress_info: "SimulationProgressInfo", sim_state: Dict,
                     calculate_results: bool) -> None:
        # pylint: disable=too-many-arguments
        """Wrapper for handling of all results."""
        self.area_result_dict = self._create_area_tree_dict(area)
        self.status = simulation_status
        self._calculate_and_update_last_market_time_slot(area)
        self.simulation_state["general"] = sim_state
        self._populate_core_stats_and_sim_state(area)
        self.simulation_progress = {
            "eta_seconds": progress_info.eta.seconds if progress_info.eta else None,
            "elapsed_time_seconds": progress_info.elapsed_time.seconds,
            "percentage_completed": int(progress_info.percentage_completed)
        }

        if calculate_results:
            self.results_handler.update(
                self.area_result_dict, self.flattened_area_core_stats_dict,
                self.current_market_time_slot_str)

            if (ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR or
                    ConstSettings.GeneralSettings.EXPORT_ENERGY_TRADE_PROFILE_HR):
                self.offer_bid_trade_hr.update(area)

        self.result_area_uuids = set()
        self.update_results_area_uuids(area)

        self._update_offer_bid_trade()

    def _update_offer_bid_trade(self) -> None:
        """Populate self.bids_offers_trades with results from flattened_area_core_stats_dict
        (for local export of statistics)."""
        self.bids_offers_trades.clear()
        if self.current_market_time_slot_str == "":
            return
        for area_uuid, area_result in self.flattened_area_core_stats_dict.items():
            self.bids_offers_trades[area_uuid] = {
                k: area_result.get(k, []) for k in ("offers", "bids", "trades")}


class CoefficientEndpointBuffer(SimulationEndpointBuffer):
    """Calculate the endpoint results for the Coefficient based market."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._scm_manager = None

    def update_coefficient_stats(
            self, area: "AreaBase", simulation_status: str,
            progress_info: "SimulationProgressInfo", sim_state: Dict,
            calculate_results: bool, scm_manager: "SCMManager") -> None:
        self._scm_manager = scm_manager
        self.current_market_time_slot_str = progress_info.current_slot_str
        super().update_stats(
            area, simulation_status, progress_info, sim_state, calculate_results)

    def _calculate_and_update_last_market_time_slot(self, area):
        pass

    def _populate_core_stats_and_sim_state(self, area: "AreaBase"):
        if area.uuid not in self.flattened_area_core_stats_dict:
            self.flattened_area_core_stats_dict[area.uuid] = {}
        if self.current_market_time_slot_str == "":
            return

        core_stats_dict = {}

        if isinstance(area.strategy, CommercialStrategy):
            if isinstance(area.strategy, FinitePowerPlant):
                core_stats_dict["production_kWh"] = area.strategy.energy_per_slot_kWh
            else:
                if area.parent.current_market is not None:
                    core_stats_dict["energy_rate"] = (
                        area.strategy.energy_rate.get(area.now, None))
        elif not area.strategy and self._scm_manager is not None:
            core_stats_dict.update(
                self._scm_manager.get_area_results(area.uuid, serializable=True))
        else:
            core_stats_dict.update(area.get_results_dict())

        self.flattened_area_core_stats_dict[area.uuid] = core_stats_dict

        self.simulation_state["areas"][area.uuid] = area.get_state()

        for child in area.children:
            self._populate_core_stats_and_sim_state(child)
