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
import csv
import logging
import pathlib
import os
import plotly.graph_objs as go
import shutil
import json
import operator
from slugify import slugify
from sortedcontainers import SortedDict

from d3a.constants import DATE_TIME_FORMAT
from d3a.models.market.market_structures import Trade, BalancingTrade, Bid, Offer, BalancingOffer
from d3a.models.area import Area
from d3a.d3a_core.sim_results.file_export_endpoints import KPI
from d3a_interface.constants_limits import ConstSettings
from d3a.d3a_core.util import constsettings_to_dict, generate_market_slot_list
from d3a.models.market.market_structures import MarketClearingState
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.state import ESSEnergyOrigin
from d3a.d3a_core.sim_results.plotly_graph import PlotlyGraph
from functools import reduce  # forward compatibility for Python 3


_log = logging.getLogger(__name__)


ENERGY_BUYER_SIGN_PLOTS = 1
ENERGY_SELLER_SIGN_PLOTS = -1 * ENERGY_BUYER_SIGN_PLOTS

alternative_pricing_subdirs = {
    0: "d3a_pricing",
    1: "no_scheme_pricing",
    2: "feed_in_tariff_pricing",
    3: "net_metering_pricing"
}

EXPORT_DEVICE_VARIABLES = ["trade_energy_kWh", "pv_production_kWh", "trade_price_eur",
                           "soc_history_%", "load_profile_kWh"]


def get_from_dict(data_dict, map_list):
    return reduce(operator.getitem, map_list, data_dict)


def mkdir_from_str(directory: str, exist_ok=True, parents=True):
    out_dir = pathlib.Path(directory)
    out_dir.mkdir(exist_ok=exist_ok, parents=parents)
    return out_dir


class ExportAndPlot:

    def __init__(self, root_area: Area, path: str, subdir: str, endpoint_buffer):
        self.area = root_area
        self.endpoint_buffer = endpoint_buffer
        self.export_data = self.endpoint_buffer.file_export_endpoints
        self.kpi = KPI()
        try:
            if path is not None:
                path = os.path.abspath(path)
            if ConstSettings.IAASettings.AlternativePricing.COMPARE_PRICING_SCHEMES is True:
                subdir = os.path.join(subdir, alternative_pricing_subdirs[
                                      ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME])

            self.rootdir = pathlib.Path(path or str(pathlib.Path.home()) + "/d3a-simulation")
            self.directory = pathlib.Path(self.rootdir, subdir)
            self.zip_filename = pathlib.Path(self.rootdir, subdir + "_results")
            mkdir_from_str(str(self.directory))
        except Exception as ex:
            _log.error("Could not open directory for csv exports: %s" % str(ex))
            return

    def export_json_data(self, directory: dir):
        json_dir = os.path.join(directory, "aggregated_results")
        mkdir_from_str(json_dir)
        settings_file = os.path.join(json_dir, "const_settings.json")
        with open(settings_file, 'w') as outfile:
            json.dump(constsettings_to_dict(), outfile, indent=2)
        kpi_file = os.path.join(json_dir, "KPI.json")
        with open(kpi_file, 'w') as outfile:
            json.dump(self.kpi.performance_index, outfile, indent=2)
        trade_file = os.path.join(json_dir, "trade-detail.json")
        with open(trade_file, 'w') as outfile:
            json.dump(self.endpoint_buffer.trade_details, outfile, indent=2)

        for key, value in self.endpoint_buffer.generate_json_report().items():
            json_file = os.path.join(json_dir, key + ".json")
            with open(json_file, 'w') as outfile:
                json.dump(value, outfile, indent=2)

    @staticmethod
    def _file_path(directory: dir, slug: str):
        file_name = ("%s.csv" % slug).replace(' ', '_')
        return directory.joinpath(file_name).as_posix()

    def export_to_zip_file(self):
        self.export(export_plots=False)
        shutil.make_archive(str(self.zip_filename), 'zip', str(self.directory))
        return str(self.zip_filename) + ".zip"

    def delete_exported_files(self):
        zip_file_with_ext = str(self.zip_filename) + ".zip"
        if os.path.isfile(zip_file_with_ext):
            os.remove(zip_file_with_ext)
        shutil.rmtree(str(self.directory))

    def export(self, export_plots=True):
        """Wrapping function, executes all export and plotting functions"""
        if export_plots:
            self.plot_dir = os.path.join(self.directory, 'plot')
            if not os.path.exists(self.plot_dir):
                os.makedirs(self.plot_dir)

            self.plot_trade_partner_cell_tower(self.area, self.plot_dir)
            self.plot_energy_profile(self.area, self.plot_dir)
            self.plot_all_unmatched_loads()
            self.plot_avg_trade_price(self.area, self.plot_dir)
            self.plot_ess_soc_history(self.area, self.plot_dir)
            self.plot_ess_energy_trace(self.area, self.plot_dir)
            if ConstSettings.GeneralSettings.EXPORT_DEVICE_PLOTS:
                self.plot_device_stats(self.area, [])
            if ConstSettings.IAASettings.MARKET_TYPE == 3 and \
                    ConstSettings.GeneralSettings.SUPPLY_DEMAND_PLOTS:
                self.plot_supply_demand_curve(self.area, self.plot_dir)
            self.move_root_plot_folder()
        self.export_json_data(self.directory)

    def data_to_csv(self, area, is_first):
        self._export_area_with_children(area, self.directory, is_first)

    def move_root_plot_folder(self):
        """
        Removes "grid" folder in self.plot_dir
        """
        old_dir = os.path.join(self.plot_dir, self.area.slug)
        if not os.path.isdir(old_dir):
            _log.error("PLOT ERROR: No plots were generated for {} under {}".
                       format(self.area.slug, self.plot_dir))
            return
        source = os.listdir(old_dir)
        for si in source:
            shutil.move(os.path.join(old_dir, si), self.plot_dir)
        shutil.rmtree(old_dir)

    def _export_area_with_children(self, area: Area, directory: dir, is_first: bool = False):
        """
        Uses the FileExportEndpoints object and writes them to csv files
        Runs _export_area_energy and _export_area_stats_csv_file
        """

        if area.children:
            subdirectory = pathlib.Path(directory, area.slug.replace(' ', '_'))
            if not subdirectory.exists():
                subdirectory.mkdir(exist_ok=True, parents=True)
            for child in area.children:
                self._export_area_with_children(child, subdirectory, is_first)

        self._export_area_stats_csv_file(area, directory, balancing=False, is_first=is_first)
        self._export_area_stats_csv_file(area, directory, balancing=True, is_first=is_first)

        if area.children:
            # TODO: To be uncommented once KPI is implemented
            # self.kpi.update_kpis_from_area(area)
            self._export_trade_csv_files(area, directory, balancing=False, is_first=is_first)
            self._export_trade_csv_files(area, directory, balancing=True, is_first=is_first)
            self._export_area_offers_bids_csv_files(area, directory, "offers", Offer,
                                                    "offer_history", area.past_markets,
                                                    is_first=is_first)
            self._export_area_offers_bids_csv_files(area, directory, "bids", Bid,
                                                    "bid_history", area.past_markets,
                                                    is_first=is_first)
            self._export_area_offers_bids_csv_files(area, directory, "balancing-offers",
                                                    BalancingOffer, "offer_history",
                                                    area.past_balancing_markets, is_first=is_first)
            if ConstSettings.IAASettings.MARKET_TYPE == 3:
                self._export_area_clearing_rate(area, directory, "market-clearing-rate", is_first)

    def _export_area_clearing_rate(self, area, directory, file_suffix, is_first):
        file_path = self._file_path(directory, f"{area.slug}-{file_suffix}")
        labels = ("slot",) + MarketClearingState._csv_fields()
        try:
            with open(file_path, 'a') as csv_file:
                writer = csv.writer(csv_file)
                if is_first:
                    writer.writerow(labels)
                for market in area.past_markets:
                    for time, clearing in market.state.clearing.items():
                        row = (market.time_slot, time, clearing[0])
                        writer.writerow(row)
        except OSError:
            _log.exception("Could not export area market_clearing_rate")

    def _export_area_offers_bids_csv_files(self, area, directory, file_suffix,
                                           offer_type, market_member, past_markets,
                                           is_first: bool):
        """
        Exports files containing individual offers, bids or balancing offers
        (*-bids/offers/balancing-offers.csv files)
        return: dict[out_keys]
        """
        file_path = self._file_path(directory, f"{area.slug}-{file_suffix}")
        labels = ("slot",) + offer_type._csv_fields()
        try:
            with open(file_path, 'a') as csv_file:
                writer = csv.writer(csv_file)
                if is_first:
                    writer.writerow(labels)
                for market in past_markets:
                    for offer in getattr(market, market_member):
                        row = (market.time_slot,) + offer._to_csv()
                        writer.writerow(row)
        except OSError:
            _log.exception("Could not export area balancing offers")

    def _export_trade_csv_files(self, area: Area, directory: dir, balancing: bool = False,
                                is_first: bool = False):
        """
        Exports files containing individual trades  (*-trades.csv  files)
        return: dict[out_keys]
        """

        if balancing:
            file_path = self._file_path(directory, "{}-balancing-trades".format(area.slug))
            labels = ("slot",) + BalancingTrade._csv_fields()
            past_markets = area.past_balancing_markets
        else:
            file_path = self._file_path(directory, "{}-trades".format(area.slug))
            labels = ("slot",) + Trade._csv_fields()
            past_markets = area.past_markets

        try:
            with open(file_path, 'a') as csv_file:
                writer = csv.writer(csv_file)
                if is_first:
                    writer.writerow(labels)
                for market in past_markets:
                    for trade in market.trades:
                        row = (market.time_slot,) + trade._to_csv()
                        writer.writerow(row)
        except OSError:
            _log.exception("Could not export area trades")

    def _export_area_stats_csv_file(self, area: Area, directory: dir,
                                    balancing: bool, is_first: bool):
        """
        Exports stats (*.csv files)
        """

        area_name = area.slug
        if balancing:
            area_name += "-balancing"
        data = self.export_data.generate_market_export_data(area, balancing)
        rows = data.rows()
        if not rows and not is_first:
            return

        try:
            with open(self._file_path(directory, area_name), 'a') as csv_file:
                writer = csv.writer(csv_file)
                if is_first:
                    writer.writerow(data.labels())
                for row in rows:
                    writer.writerow(row)
        except Exception as ex:
            _log.error("Could not export area data: %s" % str(ex))

    def plot_device_stats(self, area: Area, node_address_list: list):
        """
        Wrapper for _plot_trade_partner_cell_tower
        """
        new_node_address_list = node_address_list + [area.name]
        for child in area.children:
            if child.children:
                self.plot_device_stats(child, new_node_address_list)
            else:
                address_list = new_node_address_list + [child.name]
                self._plot_device_stats(address_list, child.strategy)

    def _plot_device_stats(self, address_list: list, device_strategy):
        """
        Plots device graphs
        """
        # Dont use the root area name for address list:
        device_address_list = address_list[1::]

        device_name = device_address_list[-1].replace(" ", "_")
        device_dict = get_from_dict(self.endpoint_buffer.device_statistics.device_stats_dict,
                                    device_address_list)

        # converting address_list into plot_dir by slugifying the members
        plot_dir = os.path.join(self.plot_dir,
                                "/".join([slugify(node).lower() for node in address_list][0:-1]))
        mkdir_from_str(plot_dir)
        output_file = os.path.join(
            plot_dir, 'device_profile_{}.html'.format(device_name))
        PlotlyGraph.plot_device_profile(device_dict, device_name, output_file, device_strategy)

    def plot_trade_partner_cell_tower(self, area: Area, subdir: str):
        """
        Wrapper for _plot_trade_partner_cell_tower
        """
        key = "cell-tower"
        new_subdir = os.path.join(subdir, area.slug)
        for child in area.children:
            if child.slug == key:
                self._plot_trade_partner_cell_tower(child.slug, subdir)
            if child.children:
                self.plot_trade_partner_cell_tower(child, new_subdir)

    def _plot_trade_partner_cell_tower(self, load: str, plot_dir: str):
        """
        Plots trade partner pie graph for the sell tower.
        """
        higt = PlotlyGraph(self.export_data.buyer_trades, load)
        higt.arrange_data()
        mkdir_from_str(plot_dir)
        higt.plot_pie_chart("Energy Trade Partners for {}".format(load),
                            os.path.join(plot_dir, "energy_trade_partner_{}.html".format(load)))

    def plot_energy_profile(self, area: Area, subdir: str):
        """
        Wrapper for _plot_energy_profile
        """

        new_subdir = os.path.join(subdir, area.slug)
        self._plot_energy_profile(new_subdir, area.name)
        for child in area.children:
            if child.children:
                self.plot_energy_profile(child, new_subdir)

    def _plot_energy_profile(self, subdir: str, market_name: str):
        """
        Plots history of energy trades
        """
        data = list()
        barmode = "relative"
        xtitle = 'Time'
        ytitle = 'Energy [kWh]'
        key = 'energy'
        title = 'Energy Trade Profile of {}'.format(market_name)
        data.extend(self._plot_energy_graph(self.export_data.traded_energy,
                                            market_name, "sold_energy_lists",
                                            "-seller", key, ENERGY_SELLER_SIGN_PLOTS))
        data.extend(self._plot_energy_graph(self.export_data.traded_energy,
                                            market_name, "bought_energy_lists",
                                            "-buyer", key, ENERGY_BUYER_SIGN_PLOTS))
        if "sold_energy_lists" in self.export_data.balancing_traded_energy[market_name]:
            data.extend(self._plot_energy_graph(self.export_data.balancing_traded_energy,
                                                market_name, "sold_energy_lists",
                                                "-balancing-seller", key,
                                                ENERGY_SELLER_SIGN_PLOTS))
            data.extend(self._plot_energy_graph(self.export_data.balancing_traded_energy,
                                                market_name, "bought_energy_lists",
                                                "-balancing-buyer", key,
                                                ENERGY_BUYER_SIGN_PLOTS))
        if len(data) == 0:
            return
        if all([len(da.y) == 0 for da in data]):
            return

        plot_dir = os.path.join(self.plot_dir, subdir)
        mkdir_from_str(plot_dir)
        output_file = os.path.join(plot_dir,
                                   'energy_profile_{}.html'.format(market_name))
        PlotlyGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def _plot_energy_graph(self, trades, market_name, agent, agent_label, key, scale_value):
        internal_data = []
        for trader in trades[market_name][agent].keys():

            graph_obj = PlotlyGraph(trades[market_name][agent][trader], key)
            graph_obj.graph_value(scale_value=scale_value)
            data_obj = go.Bar(x=list(graph_obj.umHours.keys()),
                              y=list(graph_obj.umHours.values()),
                              name=trader + agent_label)
            internal_data.append(data_obj)
        return internal_data

    def plot_all_unmatched_loads(self):
        """
        Plot unmatched loads of all loads in the configuration into one plot
        """
        unmatched_key = 'deficit [kWh]'
        data = list()
        root_name = self.area.slug
        title = 'Unmatched Loads for all devices in {}'.format(root_name)
        xtitle = 'Time'
        ytitle = 'Energy (kWh)'
        barmode = 'stack'
        load_list = [child_key for child_key in self.export_data.plot_stats.keys()
                     if unmatched_key in self.export_data.plot_stats[child_key].keys()]

        for li in load_list:
            graph_obj = PlotlyGraph(self.export_data.plot_stats[li], unmatched_key)
            if sum(graph_obj.dataset[unmatched_key]) < 1e-10:
                continue
            graph_obj.graph_value()
            data_obj = go.Bar(x=list(graph_obj.umHours.keys()),
                              y=list(graph_obj.umHours.values()),
                              name=li)
            data.append(data_obj)
        if len(data) == 0:
            return
        plot_dir = os.path.join(self.plot_dir)
        mkdir_from_str(plot_dir)
        output_file = os.path.join(plot_dir, 'unmatched_loads_{}.html'.format(root_name))
        PlotlyGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def plot_ess_soc_history(self, area, subdir):
        """
        Wrapper for _plot_ess_soc_history.
        """

        storage_key = 'charge [%]'
        new_subdir = os.path.join(subdir, area.slug)
        storage_list = [child.slug for child in area.children
                        if storage_key in self.export_data.plot_stats[child.slug].keys()]
        if storage_list is not []:
            self._plot_ess_soc_history(storage_list, new_subdir, area.slug)
        for child in area.children:
            if child.children:
                self.plot_ess_soc_history(child, new_subdir)

    def _plot_ess_soc_history(self, storage_list: list, subdir: str, root_name: str):
        """
        Plots ess soc for each knot in the hierarchy
        """

        storage_key = 'charge [%]'
        data = list()
        barmode = "relative"
        title = 'ESS SOC ({})'.format(root_name)
        xtitle = 'Time'
        ytitle = 'Charge [%]'

        for si in storage_list:
            graph_obj = PlotlyGraph(self.export_data.plot_stats[si], storage_key)
            graph_obj.graph_value()
            data_obj = go.Scatter(x=list(graph_obj.umHours.keys()),
                                  y=list(graph_obj.umHours.values()),
                                  name=si)
            data.append(data_obj)
        if len(data) == 0:
            return
        plot_dir = os.path.join(self.plot_dir, subdir)
        mkdir_from_str(plot_dir)
        output_file = os.path.join(plot_dir, 'ess_soc_history_{}.html'.format(root_name))
        PlotlyGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def plot_ess_energy_trace(self, area, subdir):
        """
        Wrapper for _plot_ess_energy_trace.
        """

        new_subdir = os.path.join(subdir, area.slug)
        storage_list = [child for child in area.children
                        if isinstance(child.strategy, StorageStrategy)]
        for element in storage_list:
            self._plot_ess_energy_trace(element.strategy.state.time_series_ess_share,
                                        new_subdir, area.slug)
        for child in area.children:
            if child.children:
                self.plot_ess_energy_trace(child, new_subdir)

    def _plot_ess_energy_trace(self, energy: dict, subdir: str, root_name: str):
        """
        Plots ess energy trace for each knot in the hierarchy
        """

        data = list()
        barmode = "stack"
        title = 'ESS ENERGY SHARE ({})'.format(root_name)
        xtitle = 'Time'
        ytitle = 'Energy [kWh]'

        temp = {ESSEnergyOrigin.UNKNOWN: {slot: 0. for slot in generate_market_slot_list()},
                ESSEnergyOrigin.LOCAL: {slot: 0. for slot in generate_market_slot_list()},
                ESSEnergyOrigin.EXTERNAL: {slot: 0. for slot in generate_market_slot_list()}}

        for time, energy_info in energy.items():
            temp[ESSEnergyOrigin.EXTERNAL][time] = energy_info[ESSEnergyOrigin.EXTERNAL]
            temp[ESSEnergyOrigin.LOCAL][time] = energy_info[ESSEnergyOrigin.LOCAL]
            temp[ESSEnergyOrigin.UNKNOWN][time] = energy_info[ESSEnergyOrigin.UNKNOWN]
        for energy_type in [ESSEnergyOrigin.EXTERNAL, ESSEnergyOrigin.LOCAL,
                            ESSEnergyOrigin.UNKNOWN]:
            data_obj = go.Bar(x=list(temp[energy_type].keys()),
                              y=list(temp[energy_type].values()),
                              name=f"{energy_type}")
            data.append(data_obj)
        if len(data) == 0:
            return
        plot_dir = os.path.join(self.plot_dir, subdir)
        mkdir_from_str(plot_dir)
        output_file = os.path.join(plot_dir, 'ess_energy_share_{}.html'.format(root_name))
        PlotlyGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def plot_supply_demand_curve(self, area, subdir):
        """
        Wrapper for _plot_supply_demand_curve
        """
        new_subdir = os.path.join(subdir, area.slug)
        self._plot_supply_demand_curve(new_subdir, area)
        for child in area.children:
            if child.children:
                self.plot_supply_demand_curve(child, new_subdir)

    def _plot_supply_demand_curve(self, subdir: str, area: Area):
        if area.slug not in self.export_data.clearing:
            return
        for market_slot, clearing in self.export_data.clearing[area.slug].items():
            data = list()
            xmax = 0
            for time_slot, supply_curve in \
                    self.export_data.cumulative_offers[area.slug][market_slot].items():
                data.append(self.render_supply_demand_curve(supply_curve, time_slot, True))
            for time_slot, demand_curve in \
                    self.export_data.cumulative_bids[area.slug][market_slot].items():
                data.append(self.render_supply_demand_curve(demand_curve, time_slot, False))

            if len(data) == 0:
                continue

            for time_slot, clearing_point in clearing.items():
                # clearing_point[0] --> Clearing-Rate
                # clearing_point[1] --> Clearing-Energy
                if len(clearing_point) != 0:
                    data_obj = go.Scatter(x=[0, clearing_point[1]],
                                          y=[clearing_point[0], clearing_point[0]],
                                          mode='lines+markers',
                                          line=dict(width=5),
                                          name=time_slot.format(DATE_TIME_FORMAT +
                                                                ' Clearing-Rate'))
                    data.append(data_obj)
                    data_obj = go.Scatter(x=[clearing_point[1], clearing_point[1]],
                                          y=[0, clearing_point[0]],
                                          mode='lines+markers',
                                          line=dict(width=5),
                                          name=time_slot.format(DATE_TIME_FORMAT +
                                                                ' Clearing-Energy'))
                    data.append(data_obj)
                    xmax = max(xmax, clearing_point[1]) * 3

            plot_dir = os.path.join(self.plot_dir, subdir, 'mcp')
            mkdir_from_str(plot_dir)
            output_file = os.path.join(plot_dir,
                                       f'supply_demand_{market_slot}.html')
            PlotlyGraph.plot_line_graph('supply_demand_curve', 'Energy (kWh)',
                                        'Rate (ct./kWh)', data, output_file, xmax)

    @classmethod
    def render_supply_demand_curve(cls, dataset, time, supply):
        rate, energy = cls.calc_supply_demand_curve(dataset, supply=supply)
        name = str(time) + '-' + ('supply' if supply else 'demand')
        data_obj = go.Scatter(x=energy,
                              y=rate,
                              mode='lines',
                              name=name)
        return data_obj

    @staticmethod
    def calc_supply_demand_curve(dataset, supply=True):
        sort_values = SortedDict(dataset)
        if supply:
            rate = list(sort_values.keys())
            energy = list(sort_values.values())
        else:
            rate = list(reversed(sort_values.keys()))
            energy = list(reversed(sort_values.values()))

        cond_rate = list()
        cond_energy = list()

        for i in range(len(energy)):

            if i == 0:
                cond_rate.append(rate[0])
                cond_energy.append(0)
                cond_rate.append(rate[0])
                cond_energy.append(energy[i])
            else:
                if energy[i-1] == energy[i] and supply:
                    continue
                cond_rate.append(rate[i])
                cond_energy.append(energy[i-1])
                cond_energy.append(energy[i])
                cond_rate.append(rate[i])
        return cond_rate, cond_energy

    def plot_avg_trade_price(self, area, subdir):
        """
        Wrapper for _plot_avg_trade_rate
        """
        if area.children:
            area_list = [area.slug]
            if area.parent:
                area_list.append(area.parent.slug)
            area_list += [ci.slug for ci in area.children]
            new_subdir = os.path.join(subdir, area.slug)
            self._plot_avg_trade_price(area_list, new_subdir)
            for child in area.children:
                self.plot_avg_trade_price(child, new_subdir)

    def _plot_avg_trade_price(self, area_list: list, subdir: str):
        """
        Plots average trade for the specified level of the hierarchy
        """
        data = list()
        barmode = 'stack'
        xtitle = "Time"
        ytitle = "Rate [ct./kWh]"
        key = 'avg trade rate [ct./kWh]'
        title = 'Average Trade Price {}'.format(area_list[0])
        for area_name in area_list:
            data.append(
                self._plot_avg_trade_graph(self.export_data.plot_stats,
                                           area_name, key, area_name)
            )
            if self.export_data.plot_balancing_stats[area_name.lower()] is not None:
                area_name_balancing = area_name.lower() + "-demand-balancing-trades"
                data.append(self._plot_avg_trade_graph(
                    self.export_data.plot_balancing_stats, area_name,
                    'avg demand balancing trade rate [ct./kWh]',
                    area_name_balancing)
                )
                area_name_balancing = area_name.lower() + "-supply-balancing-trades"
                data.append(self._plot_avg_trade_graph(
                    self.export_data.plot_balancing_stats, area_name,
                    'avg supply balancing trade rate [ct./kWh]',
                    area_name_balancing)
                )

        if all([len(da.y) == 0 for da in data]):
            return
        plot_dir = os.path.join(self.plot_dir, subdir)
        mkdir_from_str(plot_dir)
        output_file = os.path.join(plot_dir, 'average_trade_price_{}.html'.format(area_list[0]))
        PlotlyGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def _plot_avg_trade_graph(self, stats, area_name, key, label):
        graph_obj = PlotlyGraph(stats[area_name.lower()], key)
        graph_obj.graph_value()
        data_obj = go.Scatter(x=list(graph_obj.umHours.keys()),
                              y=list(graph_obj.umHours.values()),
                              name=label.lower())
        return data_obj
