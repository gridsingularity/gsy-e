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

import csv
import json
import logging
import os
import pathlib
import shutil
from typing import TYPE_CHECKING, Dict, List, Tuple

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import (
    BalancingOffer,
    BalancingTrade,
    Bid,
    MarketClearingState,
    Offer,
    Trade,
)
from gsy_framework.enums import AvailableMarketTypes, BidOfferMatchAlgoEnum
from gsy_framework.utils import mkdir_from_str
from gsy_framework.sim_results.carbon_emissions import CarbonEmissionsHandler
from pendulum import DateTime

import gsy_e.constants
from gsy_e.gsy_e_core.area_serializer import area_to_string
from gsy_e.gsy_e_core.enums import PAST_MARKET_TYPE_FILE_SUFFIX_MAPPING
from gsy_e.gsy_e_core.matching_engine_singleton import bid_offer_matcher
from gsy_e.gsy_e_core.sim_results.file_export_endpoints import file_export_endpoints_factory
from gsy_e.gsy_e_core.sim_results.results_plots import (
    PlotAverageTradePrice,
    PlotDeviceStats,
    PlotEnergyProfile,
    PlotEnergyTradeProfileHR,
    PlotESSEnergyTrace,
    PlotESSSOCHistory,
    PlotOrderInfo,
    PlotSupplyDemandCurve,
    PlotUnmatchedLoads,
)
from gsy_e.gsy_e_core.util import constsettings_to_dict, is_two_sided_market_simulation
from gsy_e.models.area import Area


if TYPE_CHECKING:
    from gsy_e.gsy_e_core.sim_results.endpoint_buffer import SimulationEndpointBuffer
    from gsy_e.models.area.scm_manager import SCMManager
    from gsy_e.models.market.future import FutureMarkets

_log = logging.getLogger(__name__)


results_field_to_json_filename_mapping = {
    "area_throughput": "area_throughput",
    "assets_info": "assets_info",
    "bills": "bills",
    "const_settings": "const_settings",
    "cumulative_bills": "cumulative_bills",
    "cumulative_grid_trades": "cumulative_grid_trades",
    "cumulative_net_energy_flow": "cumulative_net_energy_flow",
    "device_statistics": "asset_statistics",
    "job_id": "job_id",
    "kpi": "kpi",
    "market_summary": "market_summary",
    "price_energy_day": "price_energy_day",
    "progress_info": "progress_info",
    "random_seed": "random_seed",
    "simulation_state": "simulation_state",
    "status": "status",
    "trade_profile": "trade_profile",
    "imported_exported_energy": "imported_exported_energy",
    "hierarchy_self_consumption_percent": "hierarchy_self_consumption_percent",
    "carbon_emissions": "carbon_emissions",
}


# pylint: disable=too-many-instance-attributes
class ExportAndPlot:
    """Handle local export of plots and csv-files."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        root_area: Area,
        path: str,
        subdir: str,
        endpoint_buffer: "SimulationEndpointBuffer",
        country_code: str,
    ):
        self.area = root_area
        self.endpoint_buffer = endpoint_buffer
        self.file_stats_endpoint = file_export_endpoints_factory()
        self.raw_data_subdir = None
        self.country_code = country_code
        try:
            if path is not None:
                path = os.path.abspath(path)

            self.rootdir = pathlib.Path(path or str(pathlib.Path.home()) + "/gsy_e-simulation")
            self.directory = pathlib.Path(self.rootdir, subdir)
            self.zip_filename = pathlib.Path(self.rootdir, subdir + "_results")
            mkdir_from_str(str(self.directory))
            if gsy_e.constants.RETAIN_PAST_MARKET_STRATEGIES_STATE:
                self.raw_data_subdir = pathlib.Path(self.directory, "raw_data")
                if not self.raw_data_subdir.exists():
                    self.raw_data_subdir.mkdir(exist_ok=True, parents=True)
        except OSError as ex:
            _log.error("Could not open directory for csv exports: %s", str(ex))
            return

        self.plot_dir = os.path.join(self.directory, "plot")

    def _export_json_data(self) -> None:
        """Write aggregated results into JSON files."""
        json_dir = os.path.join(self.directory, "aggregated_results")
        mkdir_from_str(json_dir)
        settings_file = os.path.join(json_dir, "const_settings.json")
        with open(settings_file, "w", encoding="utf-8") as outfile:
            json.dump(constsettings_to_dict(), outfile, indent=2)
        for in_key, value in self.endpoint_buffer.generate_json_report().items():
            out_key = results_field_to_json_filename_mapping[in_key]

            if in_key == "imported_exported_energy" and self.country_code:
                carbon_emissions_handler = CarbonEmissionsHandler(
                    entsoe_api_key=os.environ.get("ENTSOE_API_SECURITY_TOKEN", None)
                )
                value = carbon_emissions_handler.calculate_from_gsy_imported_exported_energy(
                    country_code=self.country_code, imported_exported_energy=value
                )
                out_key = "carbon_emissions"

            json_file = os.path.join(json_dir, out_key + ".json")
            with open(json_file, "w", encoding="utf-8") as outfile:
                json.dump(value, outfile, indent=2)

    def _export_setup_json(self) -> None:

        setup_json_file = os.path.join(self.directory, "setup_file.json")
        setup_json = json.loads(area_to_string(self.area))
        with open(setup_json_file, "w", encoding="utf-8") as outfile:
            json.dump(setup_json, outfile, indent=2)

    @staticmethod
    def _file_path(directory: dir, area_slug: str) -> dir:
        """Return directory for the provided area_slug."""
        file_name = f"{area_slug}.csv".replace(" ", "_")
        return directory.joinpath(file_name).as_posix()

    def export(self, power_flow=None) -> None:
        """Main caller for local export of plots and csv-files."""
        if power_flow:
            power_flow.export_power_flow_results(self.plot_dir)

        if not os.path.exists(self.plot_dir):
            os.makedirs(self.plot_dir)

        self._export_json_data()
        self._export_setup_json()

        PlotEnergyProfile(self.endpoint_buffer, self.plot_dir).plot(self.area)
        PlotUnmatchedLoads(self.area, self.file_stats_endpoint, self.plot_dir).plot()
        PlotAverageTradePrice(self.file_stats_endpoint, self.plot_dir).plot(
            self.area, self.plot_dir
        )
        PlotESSSOCHistory(self.file_stats_endpoint, self.plot_dir).plot(self.area, self.plot_dir)
        PlotESSEnergyTrace(self.plot_dir).plot(self.area, self.plot_dir)
        if ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR:
            PlotOrderInfo(self.endpoint_buffer).plot_per_area_per_market_slot(
                self.area, self.plot_dir
            )
        if ConstSettings.GeneralSettings.EXPORT_DEVICE_PLOTS:
            PlotDeviceStats(self.endpoint_buffer, self.plot_dir).plot(self.area, [])
        if ConstSettings.GeneralSettings.EXPORT_ENERGY_TRADE_PROFILE_HR:
            PlotEnergyTradeProfileHR(self.endpoint_buffer, self.plot_dir).plot(
                self.area, self.plot_dir
            )
        if (
            is_two_sided_market_simulation()
            and ConstSettings.MASettings.BID_OFFER_MATCH_TYPE
            == BidOfferMatchAlgoEnum.PAY_AS_CLEAR.value
            and ConstSettings.GeneralSettings.EXPORT_SUPPLY_DEMAND_PLOTS is True
        ):
            PlotSupplyDemandCurve(self.file_stats_endpoint, self.plot_dir).plot(
                self.area, self.plot_dir
            )

        self.move_root_plot_folder()

    def data_to_csv(self, area: Area, is_first: bool) -> None:
        """Wrapper for recursive function self._export_area_with_children."""
        self._export_area_with_children(area, self.directory, is_first)

    def area_tree_summary_to_json(self, data: Dict) -> None:
        """Write area tree information to JSON file."""
        json_file = os.path.join(self.directory, "area_tree_summary.json")
        with open(json_file, "w", encoding="utf-8") as outfile:
            json.dump(data, outfile, indent=2)

    def raw_data_to_json(self, time_slot: str, data: Dict) -> None:
        """Write raw data (bids/offers/trades to local JSON files for integration tests."""
        json_file = os.path.join(self.raw_data_subdir, f"{time_slot}.json")
        with open(json_file, "w", encoding="utf-8") as outfile:
            json.dump(data, outfile, indent=2)

    def move_root_plot_folder(self) -> None:
        """
        Removes "grid" folder in self.plot_dir
        """
        old_dir = os.path.join(self.plot_dir, self.area.slug)
        if not os.path.isdir(old_dir):
            _log.error(
                "PLOT ERROR: No plots were generated for %s under %s",
                self.area.slug,
                self.plot_dir,
            )
            return
        source = os.listdir(old_dir)
        for si in source:
            shutil.move(os.path.join(old_dir, si), self.plot_dir)
        shutil.rmtree(old_dir)

    def _export_spot_markets_stats(self, area: Area, directory: dir, is_first: bool) -> None:
        """Export bids, offers, trades, statistics csv-files for all spot markets."""
        self._export_area_stats_csv_file(area, directory, AvailableMarketTypes.SPOT, is_first)
        if not area.children:
            return
        self._export_offers_bids_trades_to_csv_files(
            past_markets=area.past_markets,
            market_member="trades",
            file_path=self._file_path(directory, f"{area.slug}-trades"),
            labels=("slot",) + Trade.csv_fields(),
            is_first=is_first,
        )

        self._export_offers_bids_trades_to_csv_files(
            past_markets=area.past_markets,
            market_member="offer_history",
            file_path=self._file_path(directory, f"{area.slug}-offers"),
            labels=("slot",) + Offer.csv_fields(),
            is_first=is_first,
        )

        self._export_offers_bids_trades_to_csv_files(
            past_markets=area.past_markets,
            market_member="bid_history",
            file_path=self._file_path(directory, f"{area.slug}-bids"),
            labels=("slot",) + Bid.csv_fields(),
            is_first=is_first,
        )

    def _export_settlement_markets_stats(self, area: Area, directory: dir, is_first: bool) -> None:
        """Export bids, offers, trades, statistics csv-files for all settlement markets."""
        if not ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS:
            return
        self._export_area_stats_csv_file(
            area, directory, AvailableMarketTypes.SETTLEMENT, is_first
        )
        if not area.children:
            return
        self._export_offers_bids_trades_to_csv_files(
            past_markets=area.past_settlement_markets.values(),
            market_member="trades",
            file_path=self._file_path(directory, f"{area.slug}-settlement-trades"),
            labels=("slot",) + Trade.csv_fields(),
            is_first=is_first,
        )
        self._export_offers_bids_trades_to_csv_files(
            past_markets=area.past_settlement_markets.values(),
            market_member="offer_history",
            file_path=self._file_path(directory, f"{area.slug}-settlement-offers"),
            labels=("slot",) + Offer.csv_fields(),
            is_first=is_first,
        )
        self._export_offers_bids_trades_to_csv_files(
            past_markets=area.past_settlement_markets.values(),
            market_member="bid_history",
            file_path=self._file_path(directory, f"{area.slug}-settlement-bids"),
            labels=("slot",) + Bid.csv_fields(),
            is_first=is_first,
        )

    def _export_future_markets_stats(self, area: Area, directory: dir, is_first: bool) -> None:
        """Export bids, offers, trades, statistics csv-files for all settlement markets."""
        if (
            ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS <= 0
            or not area.future_markets
        ):
            return
        self._export_area_stats_csv_file(area, directory, AvailableMarketTypes.FUTURE, is_first)
        if not area.children:
            return

        self._export_future_offers_bid_trades_to_csv_files(
            future_markets=area.future_markets,
            market_member="trades",
            file_path=self._file_path(directory, f"{area.slug}-future-trades"),
            labels=("slot",) + Trade.csv_fields(),
            is_first=is_first,
        )
        self._export_future_offers_bid_trades_to_csv_files(
            future_markets=area.future_markets,
            market_member="offer_history",
            file_path=self._file_path(directory, f"{area.slug}-future-offers"),
            labels=("slot",) + Offer.csv_fields(),
            is_first=is_first,
        )
        self._export_future_offers_bid_trades_to_csv_files(
            future_markets=area.future_markets,
            market_member="bid_history",
            file_path=self._file_path(directory, f"{area.slug}-future-bids"),
            labels=("slot",) + Bid.csv_fields(),
            is_first=is_first,
        )

    def _export_balancing_markets_stats(self, area: Area, directory: dir, is_first: bool) -> None:
        """Export bids, offers, trades, statistics csv-files for all balancing markets."""
        if not ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
            return
        self._export_area_stats_csv_file(area, directory, AvailableMarketTypes.BALANCING, is_first)
        if not area.children:
            return
        self._export_offers_bids_trades_to_csv_files(
            past_markets=area.past_balancing_markets,
            market_member="trades",
            file_path=self._file_path(directory, f"{area.slug}-balancing-trades"),
            labels=("slot",) + BalancingTrade.csv_fields(),
            is_first=is_first,
        )

        self._export_offers_bids_trades_to_csv_files(
            past_markets=area.past_balancing_markets,
            market_member="offer_history",
            file_path=self._file_path(directory, f"{area.slug}-balancing-offers"),
            labels=("slot",) + BalancingOffer.csv_fields(),
            is_first=is_first,
        )

    def _export_area_with_children(
        self, area: Area, directory: dir, is_first: bool = False
    ) -> None:
        """
        Uses the FileExportEndpoints object and writes them to csv files
        Runs _export_area_energy and _export_area_stats_csv_file
        """
        if area.children:
            subdirectory = pathlib.Path(directory, area.slug.replace(" ", "_"))
            if not subdirectory.exists():
                subdirectory.mkdir(exist_ok=True, parents=True)
            for child in area.children:
                self._export_area_with_children(child, subdirectory, is_first)

        self._export_spot_markets_stats(area, directory, is_first)
        self._export_settlement_markets_stats(area, directory, is_first)
        self._export_future_markets_stats(area, directory, is_first)
        self._export_balancing_markets_stats(area, directory, is_first)

        if area.children:
            if (
                is_two_sided_market_simulation()
                and ConstSettings.MASettings.BID_OFFER_MATCH_TYPE
                == BidOfferMatchAlgoEnum.PAY_AS_CLEAR.value
            ):
                self._export_area_clearing_rate(area, directory, "market-clearing-rate", is_first)

    def _export_area_clearing_rate(self, area, directory, file_suffix, is_first) -> None:
        """Export clearing rate as in a csv-file."""
        file_path = self._file_path(directory, f"{area.slug}-{file_suffix}")
        labels = ("slot",) + MarketClearingState.csv_fields()
        try:
            with open(file_path, "a", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                if is_first:
                    writer.writerow(labels)
                for market in area.past_markets:
                    market_clearing = bid_offer_matcher.matcher.match_algorithm.state.clearing.get(
                        market.id
                    )
                    if market_clearing is None:
                        continue
                    for time, clearing in market_clearing.items():
                        if market.time_slot > time:
                            row = (market.time_slot_str, time, clearing)
                            writer.writerow(row)
        except OSError:
            _log.exception("Could not export area market_clearing_rate")

    @staticmethod
    def _export_future_offers_bid_trades_to_csv_files(
        future_markets: "FutureMarkets",
        market_member: str,
        file_path: dir,
        labels: Tuple,
        is_first: bool = False,
    ) -> None:
        """
        Export files containing individual future offers, bids (*-bids*/*-offers*.csv files).
        """
        try:
            with open(file_path, "a", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                if is_first:
                    writer.writerow(labels)
                if not future_markets.market_time_slots:
                    return
                time_slot = future_markets.market_time_slots[0]
                for offer_or_bid in getattr(future_markets, market_member):
                    if offer_or_bid.time_slot == time_slot:
                        row = (time_slot,) + offer_or_bid.csv_values()
                        writer.writerow(row)
        except OSError:
            _log.exception("Could not export offers, bids, trades")

    @staticmethod
    def _export_offers_bids_trades_to_csv_files(
        past_markets: List,
        market_member: str,
        file_path: dir,
        labels: Tuple,
        is_first: bool = False,
    ) -> None:
        """Export files containing individual offers, bids (*-bids*/*-offers*.csv files)."""
        try:
            with open(file_path, "a", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                if is_first:
                    writer.writerow(labels)
                for market in past_markets:
                    for offer_or_bid in getattr(market, market_member):
                        row = (market.time_slot,) + offer_or_bid.csv_values()
                        writer.writerow(row)
        except OSError:
            _log.exception("Could not export offers, bids, trades")

    def _export_area_stats_csv_file(
        self, area: Area, directory: dir, past_market_type: AvailableMarketTypes, is_first: bool
    ) -> None:
        """Export trade statistics in *.csv files."""
        file_name = f"{area.slug}{PAST_MARKET_TYPE_FILE_SUFFIX_MAPPING[past_market_type]}"
        data = self.file_stats_endpoint.export_data_factory(area, past_market_type)
        rows = data.rows
        if not rows and not is_first:
            return

        try:
            with open(self._file_path(directory, file_name), "a", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                if is_first:
                    writer.writerow(data.labels)
                for row in rows:
                    writer.writerow(row)
        except OSError:
            _log.exception("Could not export area data.")


# pylint: disable=missing-class-docstring,arguments-differ,attribute-defined-outside-init


class CoefficientExportAndPlot(ExportAndPlot):

    def data_to_csv(
        self,
        area: "Area",
        time_slot: DateTime,
        is_first: bool = True,
        scm_manager: "SCMManager" = None,
    ):  # pylint: disable=arguments-renamed
        self._time_slot = time_slot
        self._scm_manager = scm_manager
        self._export_area_with_children(area, self.directory, is_first)

    def _export_area_with_children(
        self, area: Area, directory: dir, is_first: bool = False
    ) -> None:
        """
        Uses the FileExportEndpoints object and writes them to csv files
        Runs _export_area_energy and _export_area_stats_csv_file
        """
        if area.children:
            subdirectory = pathlib.Path(directory, area.slug.replace(" ", "_"))
            if not subdirectory.exists():
                subdirectory.mkdir(exist_ok=True, parents=True)
            for child in area.children:
                self._export_area_with_children(child, subdirectory, is_first)

            self._export_scm_trades_to_csv_files(
                area_uuid=area.uuid,
                file_path=self._file_path(directory, f"{area.slug}-trades"),
                labels=("slot",) + Trade.csv_fields(),
                is_first=is_first,
            )

        self._export_area_stats_csv_file(area, directory, AvailableMarketTypes.SPOT, is_first)

    def _export_scm_trades_to_csv_files(
        self, area_uuid: str, file_path: dir, labels: Tuple, is_first: bool = False
    ) -> None:
        """Export files containing individual SCM trades."""
        try:
            with open(file_path, "a", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                if is_first:
                    writer.writerow(labels)
                if not self._scm_manager:
                    return
                after_meter_data = self._scm_manager.get_after_meter_data(area_uuid)
                if not after_meter_data:
                    return

                for trade in after_meter_data.trades:
                    row = (self._time_slot,) + trade.csv_values()
                    writer.writerow(row)
        except OSError:
            _log.exception("Could not export offers, bids, trades")
