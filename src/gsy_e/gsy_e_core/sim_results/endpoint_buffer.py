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
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, Iterable, List

from gsy_framework.constants_limits import (
    DATE_TIME_FORMAT, DATE_TIME_UI_FORMAT, ConstSettings, GlobalConfig)
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.schema.validators import get_schema_validator
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


class SimulationResultValidator:
    """Validator class to be used by SimulationEndpointBuffer and CoefficientEndpointBuffer."""
    def __init__(self, is_scm: bool):
        self.is_scm = is_scm

        if self.is_scm:
            self.simulation_raw_data_validator = get_schema_validator(
                "scm_simulation_raw_data")
        else:
            self.simulation_raw_data_validator = get_schema_validator(
                "simulation_raw_data")
        self.simulation_configuration_tree_validator = get_schema_validator(
            "results_configuration_tree")
        self.simulation_state_validator = get_schema_validator("simulation_state")

    def validate_simulation_raw_data(self, data: Dict):
        """Validate flattened_area_core_stats_dict."""
        self.simulation_raw_data_validator.validate(data=data, raise_exception=True)

    def validate_configuration_tree(self, data: Dict):
        """Validate configuration_tree dict."""
        self.simulation_configuration_tree_validator.validate(data=data, raise_exception=True)

    def validate_simulation_state(self, data: Dict):
        """Validate simulation state."""
        self.simulation_state_validator.validate(data, raise_exception=True)


# pylint: disable=too-many-instance-attributes
# pylint: disable=logging-too-many-args
class SimulationEndpointBuffer:
    """Handles collecting and buffering of all results for all areas."""

    def __init__(self, job_id, random_seed, area, should_export_plots):
        self.job_id = job_id
        self.result_area_uuids = set()
        self.spot_market_time_slot_str = ""
        self.spot_market_ui_time_slot_str = ""
        self.spot_market_time_slot_unix = None
        self.spot_market_time_slot = None
        self.random_seed = random_seed if random_seed is not None else ""
        self.status = ""
        self.area_result_dict = self._create_area_tree_dict(area)
        self.flattened_area_core_stats_dict = {}
        self.simulation_progress = {
            "eta_seconds": 0,
            "elapsed_time_seconds": 0,
            "percentage_completed": 0
        }

        self.results_handler = self._create_endpoint_buffer(should_export_plots)
        self.simulation_state = {"general": {}, "areas": {}}

        if (ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR or
                ConstSettings.GeneralSettings.EXPORT_ENERGY_TRADE_PROFILE_HR):
            self.offer_bid_trade_hr = OfferBidTradeGraphStats()

        self.results_validator = None
        self._create_results_validator()

    def prepare_results_for_publish(self) -> Dict:
        """Validate, serialise and check size of the results before sending to gsy-web."""
        result_report = self._generate_result_report()

        message_size = get_json_dict_memory_allocation_size(result_report)
        if message_size > 64000:
            logging.error("Do not publish message bigger than 64 MB, "
                          "current message size %s MB.", (message_size / 1000.0))
            return {}
        logging.debug("Publishing %s KB of data via Redis.", message_size)
        return result_report

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
                self.spot_market_time_slot_str)

            if (ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR or
                    ConstSettings.GeneralSettings.EXPORT_ENERGY_TRADE_PROFILE_HR):
                self.offer_bid_trade_hr.update(area)

        self.result_area_uuids = set()
        self._update_results_area_uuids(area)

        self.validate_results()

    def validate_results(self):
        """Validate updated stats and raise exceptions if they are not valid."""
        self.results_validator.validate_simulation_raw_data(self.flattened_area_core_stats_dict)

        self.results_validator.validate_configuration_tree(self.area_result_dict)
        self.results_validator.validate_simulation_state(self.simulation_state)

    def _create_results_validator(self):
        self.results_validator = SimulationResultValidator(is_scm=False)

    @staticmethod
    def _create_endpoint_buffer(should_export_plots):
        return ResultsHandler(should_export_plots)

    def _generate_result_report(self) -> Dict:
        """Create dict that contains all statistics that are sent to the gsy-web."""
        return {
            "job_id": self.job_id,
            "current_market": self.spot_market_time_slot_str,
            "current_market_ui_time_slot_str": self.spot_market_ui_time_slot_str,
            "random_seed": self.random_seed,
            "status": self.status,
            "progress_info": self.simulation_progress,
            "results_area_uuids": list(self.result_area_uuids),
            "simulation_state": self.simulation_state,
            "simulation_raw_data": self.flattened_area_core_stats_dict,
            "configuration_tree": self.area_result_dict
        }

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

        if (ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS and
                target_area.strategy is not None):
            # pylint: disable=protected-access
            area_dict["capacity_kW"] = target_area.strategy._energy_params.capacity_kW

        return area_dict

    def _create_area_tree_dict(self, area: "AreaBase") -> Dict:
        """Create a tree that mirrors the setup architecture and contains basic information."""
        area_result_dict = self._structure_results_from_area_object(area)
        for child in area.children:
            area_result_dict["children"].append(
                self._create_area_tree_dict(child)
            )
        return area_result_dict

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

    @staticmethod
    def _get_current_forward_orders_from_timeslot(
            forward_orders: Iterable,
            market_time_slot: DateTime,
            area: "Area") -> List:
        """Filter orders that have happened in the current simulation time for
        the specified market time slot."""
        current_time_slot = area.now
        last_time_slot = area.now - area.config.slot_length
        return [order.serializable_dict()
                for order in forward_orders
                if order.time_slot == market_time_slot and
                last_time_slot <= order.creation_time < current_time_slot]

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

    def _read_forward_markets_stats_to_dict(
            self, area: "Area") -> Dict[AvailableMarketTypes, Dict[str, Dict]]:
        """Read forward markets and return market_stats in a dict."""

        stats_dict = defaultdict(dict)
        if not area.forward_markets:
            return stats_dict

        for market_type, market in area.forward_markets.items():
            for time_slot in market.market_time_slots:
                time_slot_str = time_slot.format(DATE_TIME_FORMAT)
                stats_dict[market_type.value][time_slot_str] = {
                    # only export unmatched open bids/offers
                    "bids": self._get_current_forward_orders_from_timeslot(
                        market.bids.values(), time_slot, area),
                    "offers": self._get_current_forward_orders_from_timeslot(
                        market.offers.values(), time_slot, area),
                    "trades": self._get_current_forward_orders_from_timeslot(
                        market.trades, time_slot, area),
                    "market_fee": market.market_fee,
                    "const_fee_rate": (
                        market.const_fee_rate if market.const_fee_rate is not None else 0.),
                    "feed_in_tariff": get_feed_in_tariff_rate_from_config(
                        market, time_slot=time_slot),
                    "market_maker_rate": get_market_maker_rate_from_config(
                        market, time_slot=time_slot)
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
        if self.spot_market_time_slot_str == "":
            return
        core_stats_dict = {"bids": [], "offers": [], "trades": [], "market_fee": 0.0}

        if area.spot_market:
            if not ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS:
                # Spot market cannot operate in parallel with the forward markets
                core_stats_dict.update(self._read_market_stats_to_dict(area.spot_market))

            if ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS:
                core_stats_dict["settlement_market_stats"] = (
                    self._read_settlement_markets_stats_to_dict(area))
            if ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS > 0:
                core_stats_dict["future_market_stats"] = (
                    self._read_future_markets_stats_to_dict(area)
                )
            if ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS:
                core_stats_dict["forward_market_stats"] = (
                    self._read_forward_markets_stats_to_dict(area)
                )

        if (isinstance(area.strategy, CommercialStrategy) and not
                ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS):
            if isinstance(area.strategy, FinitePowerPlant):
                core_stats_dict["production_kWh"] = area.strategy.energy_per_slot_kWh
                if area.parent.spot_market is not None:
                    for trade in area.strategy.trades[area.parent.spot_market]:
                        core_stats_dict["trades"].append(trade.serializable_dict())
            else:
                if area.parent.spot_market is not None:
                    core_stats_dict["energy_rate"] = (
                        area.strategy.energy_rate.get(area.parent.spot_market.time_slot, None))
                    for trade in area.strategy.trades[area.parent.spot_market]:
                        core_stats_dict["trades"].append(trade.serializable_dict())
        elif not ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS:
            core_stats_dict.update(area.get_results_dict())
            if area.parent and area.parent.spot_market and area.strategy:
                for trade in area.strategy.trades[area.parent.spot_market]:
                    core_stats_dict["trades"].append(trade.serializable_dict())

        self.flattened_area_core_stats_dict[area.uuid] = core_stats_dict

        self.simulation_state["areas"][area.uuid] = area.get_state()

        for child in area.children:
            self._populate_core_stats_and_sim_state(child)

    def _calculate_and_update_last_market_time_slot(self, area: "Area"):
        is_initial_spot_market_on_cn = (
                GlobalConfig.is_canary_network() and
                (area.spot_market is None or
                 (area.spot_market and
                  area.spot_market.time_slot -
                  area.current_market.time_slot > area.config.slot_length)))
        if area.spot_market is not None and not is_initial_spot_market_on_cn:
            self.spot_market_time_slot_str = area.spot_market.time_slot_str
            self.spot_market_ui_time_slot_str = (
                area.spot_market.time_slot.format(DATE_TIME_UI_FORMAT))
            self.spot_market_time_slot_unix = area.spot_market.time_slot.timestamp()
            self.spot_market_time_slot = area.spot_market.time_slot

    def _update_results_area_uuids(self, area: "AreaBase") -> None:
        """Populate a set of area uuids that contribute to the stats."""
        if area.strategy is not None or (area.strategy is None and area.children):
            self.result_area_uuids.update({area.uuid})
        for child in area.children:
            self._update_results_area_uuids(child)


class CoefficientEndpointBuffer(SimulationEndpointBuffer):
    """Calculate the endpoint results for the Coefficient based market."""

    def __init__(self, *args, **kwargs):
        self._scm_past_slots = kwargs.pop("scm_past_slots", False)
        super().__init__(*args, **kwargs)
        self._scm_manager = None

    def _generate_result_report(self) -> Dict:
        """Create dict that contains all statistics that are sent to the gsy-web."""
        result_dict = super()._generate_result_report()
        return {
            "scm_past_slots": self._scm_past_slots,
            **result_dict
        }

    def update_coefficient_stats(  # pylint: disable=too-many-arguments
            self, area: "AreaBase", simulation_status: str,
            progress_info: "SimulationProgressInfo", sim_state: Dict,
            calculate_results: bool, scm_manager: "SCMManager") -> None:
        """Update the stats of the SCM endpoint buffer."""
        self._scm_manager = scm_manager

        self.spot_market_time_slot_str = progress_info.current_slot_str
        if progress_info.current_slot_time:
            self.spot_market_time_slot = progress_info.current_slot_time
            self.spot_market_time_slot_unix = progress_info.current_slot_time.timestamp()

        super().update_stats(
            area, simulation_status, progress_info, sim_state, calculate_results)

    def _create_results_validator(self):
        self.results_validator = SimulationResultValidator(is_scm=True)

    def _create_endpoint_buffer(self, should_export_plots):
        return ResultsHandler(should_export_plots, is_scm=True)

    def _calculate_and_update_last_market_time_slot(self, area):
        pass

    def _populate_core_stats_and_sim_state(self, area: "AreaBase"):
        if area.uuid not in self.flattened_area_core_stats_dict:
            self.flattened_area_core_stats_dict[area.uuid] = {}
        if self.spot_market_time_slot_str == "":
            return

        core_stats_dict = {}

        if isinstance(area.strategy, CommercialStrategy):
            if isinstance(area.strategy, FinitePowerPlant):
                core_stats_dict["production_kWh"] = area.strategy.energy_per_slot_kWh
            else:
                if area.parent.spot_market is not None:
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
