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
import plotly as py
import plotly.graph_objs as go
import pendulum
import shutil
import json
import operator
from slugify import slugify
from sortedcontainers import SortedDict
from d3a.constants import DATE_TIME_FORMAT

from d3a.constants import TIME_ZONE
from d3a.models.market.market_structures import Trade, BalancingTrade, Bid, Offer, BalancingOffer
from d3a.models.area import Area
from d3a.d3a_core.sim_results.file_export_endpoints import FileExportEndpoints, KPI
from d3a.models.const import ConstSettings
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.d3a_core.util import constsettings_to_dict
from d3a.models.market.market_structures import MarketClearingState
from functools import reduce  # forward compatibility for Python 3
from d3a import limit_float_precision

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

green = 'rgba(20,150,20, alpha)'
purple = 'rgb(156, 110, 177, alpha)'
blue = 'rgba(0,0,200,alpha)'

DEVICE_PLOT_COLORS = {"trade_energy_kWh": purple,
                      "pv_production_kWh": green,
                      "load_profile_kWh": green,
                      "soc_history_%": green,
                      "trade_price_eur": blue}

DEVICE_YAXIS = {"trade_energy_kWh": 'Demand/Traded [kWh]',
                "pv_production_kWh": 'PV Production [kWh]',
                "load_profile_kWh": 'Load Profile [kWh]',
                "soc_history_%": 'State of Charge [%]',
                "trade_price_eur": 'Energy Rate [EUR/kWh]'}


def _invert(inlist: list): return [-1 * l for l in inlist]


def _get_color(key, alpha):
    return DEVICE_PLOT_COLORS[key].replace("alpha", str(alpha))


def get_from_dict(data_dict, map_list):
    return reduce(operator.getitem, map_list, data_dict)


def mkdir_from_str(directory: str, exist_ok=True, parents=True):
    out_dir = pathlib.Path(directory)
    out_dir.mkdir(exist_ok=exist_ok, parents=parents)
    return out_dir


class ExportAndPlot:

    def __init__(self, root_area: Area, path: str, subdir: str, endpoint_buffer):
        self.area = root_area
        self.export_data = FileExportEndpoints(root_area)
        self.endpoint_buffer = endpoint_buffer
        self.kpi = KPI()
        try:
            if path is not None:
                path = os.path.abspath(path)
            if ConstSettings.IAASettings.AlternativePricing.COMPARE_PRICING_SCHEMES is True:
                subdir = os.path.join(subdir, alternative_pricing_subdirs[
                                      ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME])

            self.directory = pathlib.Path(path or "~/d3a-simulation", subdir).expanduser()
            mkdir_from_str(str(self.directory.mkdir))
        except Exception as ex:
            _log.error("Could not open directory for csv exports: %s" % str(ex))
            return

        self.plot_dir = os.path.join(self.directory, 'plot')
        if not os.path.exists(self.plot_dir):
            os.makedirs(self.plot_dir)

        self.export()
        self.export_json_data(self.directory)

    def export_json_data(self, directory: dir):
        json_dir = os.path.join(directory, "aggregated_results")
        mkdir_from_str(json_dir)
        settings_file = os.path.join(json_dir, "const_settings")
        with open(settings_file, 'w') as outfile:
            json.dump(constsettings_to_dict(), outfile, indent=2)
        kpi_file = os.path.join(json_dir, "KPI")
        with open(kpi_file, 'w') as outfile:
            json.dump(self.kpi.performance_index, outfile, indent=2)
        trade_file = os.path.join(json_dir, "trade-detail")
        with open(trade_file, 'w') as outfile:
            json.dump(self.endpoint_buffer.trade_details, outfile, indent=2)

        for key, value in self.endpoint_buffer.generate_json_report().items():
            json_file = os.path.join(json_dir, key)
            with open(json_file, 'w') as outfile:
                json.dump(value, outfile, indent=2)

    @staticmethod
    def _file_path(directory: dir, slug: str):
        file_name = ("%s.csv" % slug).replace(' ', '_')
        return directory.joinpath(file_name).as_posix()

    def export(self):
        """Wrapping function, executes all export and plotting functions"""

        self._export_area_with_children(self.area, self.directory)
        self.plot_trade_partner_cell_tower(self.area, self.plot_dir)
        self.plot_energy_profile(self.area, self.plot_dir)
        self.plot_all_unmatched_loads()
        self.plot_avg_trade_price(self.area, self.plot_dir)
        self.plot_ess_soc_history(self.area, self.plot_dir)
        if ConstSettings.GeneralSettings.EXPORT_DEVICE_PLOTS:
            self.plot_device_stats(self.area, [])
        if ConstSettings.IAASettings.MARKET_TYPE == 3 and \
                ConstSettings.GeneralSettings.SUPPLY_DEMAND_PLOTS:
            self.plot_supply_demand_curve(self.area, self.plot_dir)
        self.move_root_plot_folder()

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

    def _export_area_with_children(self, area: Area, directory: dir):
        """
        Uses the FileExportEndpoints object and writes them to csv files
        Runs _export_area_energy and _export_area_stats_csv_file
        """
        if area.children:
            subdirectory = pathlib.Path(directory, area.slug.replace(' ', '_'))
            subdirectory.mkdir(exist_ok=True, parents=True)
            for child in area.children:
                self._export_area_with_children(child, subdirectory)

        self._export_area_stats_csv_file(area, directory, balancing=False)
        self._export_area_stats_csv_file(area, directory, balancing=True)
        if area.children:
            self.kpi.update_kpis_from_area(area)
            self._export_trade_csv_files(area, directory, balancing=False)
            self._export_trade_csv_files(area, directory, balancing=True)
            self._export_area_offers_bids_csv_files(area, directory, "offers",
                                                    Offer, "offer_history", area.past_markets)
            self._export_area_offers_bids_csv_files(area, directory, "bids",
                                                    Bid, "bid_history", area.past_markets)
            self._export_area_offers_bids_csv_files(area, directory, "balancing-offers",
                                                    BalancingOffer, "offer_history",
                                                    area.past_balancing_markets)
            if ConstSettings.IAASettings.MARKET_TYPE == 3:
                self._export_area_clearing_rate(area, directory, "market-clearing-rate")

    def _export_area_clearing_rate(self, area, directory, file_suffix):
        file_path = self._file_path(directory, f"{area.slug}-{file_suffix}")
        labels = ("slot",) + MarketClearingState._csv_fields()
        try:
            with open(file_path, 'w') as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(labels)
                for market in area.past_markets:
                    for time, clearing in market.state.clearing.items():
                        row = (market.time_slot, time, clearing[0])
                        writer.writerow(row)
        except OSError:
            _log.exception("Could not export area market_clearing_rate")

    def _export_area_offers_bids_csv_files(self, area, directory, file_suffix,
                                           offer_type, market_member, past_markets):
        """
        Exports files containing individual offers, bids or balancing offers
        (*-bids/offers/balancing-offers.csv files)
        return: dict[out_keys]
        """
        file_path = self._file_path(directory, f"{area.slug}-{file_suffix}")
        labels = ("slot",) + offer_type._csv_fields()
        try:
            with open(file_path, 'w') as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(labels)
                for market in past_markets:
                    for offer in getattr(market, market_member):
                        row = (market.time_slot,) + offer._to_csv()
                        writer.writerow(row)
        except OSError:
            _log.exception("Could not export area balancing offers")

    def _export_trade_csv_files(self, area: Area, directory: dir, balancing: bool = False):
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
            with open(file_path, 'w') as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(labels)
                for market in past_markets:
                    for trade in market.trades:
                        row = (market.time_slot,) + trade._to_csv()
                        writer.writerow(row)
        except OSError:
            _log.exception("Could not export area trades")

    def _export_area_stats_csv_file(self, area: Area, directory: dir, balancing: bool):
        """
        Exports stats (*.csv files)
        """

        area_name = area.slug
        if balancing:
            area_name += "-balancing"
        data = self.export_data.generate_market_export_data(area, balancing)
        rows = data.rows()
        if not rows:
            return

        try:
            with open(self._file_path(directory, area_name), 'w') as csv_file:
                writer = csv.writer(csv_file)
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
        PlotlyGraph._plot_device_profile(device_dict, device_name, output_file, device_strategy)

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
        self._plot_energy_profile(new_subdir, area.slug)
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
        data.extend(self._plot_energy_graph(self.export_data.balancing_traded_energy,
                                            market_name, "sold_energy_lists",
                                            "-balancing-seller", key, ENERGY_SELLER_SIGN_PLOTS))
        data.extend(self._plot_energy_graph(self.export_data.balancing_traded_energy,
                                            market_name, "bought_energy_lists",
                                            "-balancing-buyer", key, ENERGY_BUYER_SIGN_PLOTS))
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

        for past_market in area.past_markets:
            data = list()
            xmax = 0
            for time_slot, supply_curve in past_market.state.cumulative_offers.items():
                data.append(PlotlyGraph._line_plot(supply_curve, time_slot, True))
            for time_slot, demand_curve in past_market.state.cumulative_bids.items():
                data.append(PlotlyGraph._line_plot(demand_curve, time_slot, False))

            if len(data) == 0:
                continue

            for time_slot, clearing_point in past_market.state.clearing.items():
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
                                                                'Clearing-Energy'))
                    data.append(data_obj)
                    xmax = max(xmax, clearing_point[1]) * 3

            plot_dir = os.path.join(self.plot_dir, subdir, 'mcp')
            mkdir_from_str(plot_dir)
            output_file = os.path.join(plot_dir,
                                       f'supply_demand_{past_market.time_slot_str}.html')
            PlotlyGraph.plot_line_graph('supply_demand_curve', 'Energy (kWh)',
                                        'Rate (ct./kWh)', data, output_file, xmax)

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


class PlotlyGraph:
    def __init__(self, dataset: dict, key: str):
        self.key = key
        self.dataset = dataset
        self.umHours = dict()
        self.rate = list()
        self.energy = list()
        self.trade_history = dict()

    @staticmethod
    def _line_plot(curve_point, time, supply):
        graph_obj = PlotlyGraph(curve_point, time)
        graph_obj.supply_demand_curve(supply)
        name = str(time) + '-' + ('supply' if supply else 'demand')
        data_obj = go.Scatter(x=list(graph_obj.energy),
                              y=list(graph_obj.rate),
                              mode='lines',
                              name=name)
        return data_obj

    def supply_demand_curve(self, supply=True):
        sort_values = SortedDict(self.dataset)
        if supply:
            self.rate = list(sort_values.keys())
            self.energy = list(sort_values.values())
        else:
            self.rate = list(reversed(sort_values.keys()))
            self.energy = list(reversed(sort_values.values()))

        cond_rate = list()
        cond_energy = list()

        for i in range(len(self.energy)):

            if i == 0:
                cond_rate.append(self.rate[0])
                cond_energy.append(0)
                cond_rate.append(self.rate[0])
                cond_energy.append(self.energy[i])
            else:
                if self.energy[i-1] == self.energy[i] and supply:
                    continue
                cond_rate.append(self.rate[i])
                cond_energy.append(self.energy[i-1])
                cond_energy.append(self.energy[i])
                cond_rate.append(self.rate[i])
        self.rate = list()
        self.rate = cond_rate
        self.energy = list()
        self.energy = cond_energy

    @staticmethod
    def common_layout(barmode: str, title: str, ytitle: str, xtitle: str, xrange: list):
        return go.Layout(
            autosize=False,
            width=1200,
            height=700,
            barmode=barmode,
            title=title,
            yaxis=dict(
                title=ytitle
            ),
            xaxis=dict(
                title=xtitle,
                range=xrange
            ),
            font=dict(
                size=16
            ),
            showlegend=True
        )

    def graph_value(self, scale_value=1):
        try:
            self.dataset[self.key]
        except KeyError:
            pass
        else:
            for de in range(len(self.dataset[self.key])):
                if self.dataset[self.key][de] != 0:
                    if self.dataset[self.key][de] == "-":
                        self.umHours[self.dataset['slot'][de]] = 0.0
                    else:
                        self.umHours[self.dataset['slot'][de]] = \
                            round(self.dataset[self.key][de], 5) * scale_value

    @staticmethod
    def modify_time_axis(data: dict, title: str):
        """
        Changes timezone of pendulum x-values to 'UTC' and determines the list of days
        in order to return the time_range for the plot
        """
        day_set = set()
        for di in range(len(data)):
            time_list = data[di]["x"]
            for ti in time_list:
                day_set.add(pendulum.datetime(ti.year, ti.month, ti.day, tz=TIME_ZONE))

        day_list = sorted(list(day_set))
        if len(day_list) == 0:
            raise ValueError("There is no time information in plot {}".format(title))

        start_time = pendulum.datetime(day_list[0].year, day_list[0].month, day_list[0].day,
                                       0, 0, 0, tz=TIME_ZONE)
        end_time = pendulum.datetime(day_list[-1].year, day_list[-1].month, day_list[-1].day,
                                     23, 59, 59, tz=TIME_ZONE)

        return [start_time, end_time], data

    @classmethod
    def plot_bar_graph(cls, barmode: str, title: str, xtitle: str, ytitle: str, data, iname: str):
        try:
            time_range, data = cls.modify_time_axis(data, title)
        except ValueError:
            return

        layout = cls.common_layout(barmode, title, ytitle, xtitle, time_range)

        fig = go.Figure(data=data, layout=layout)
        py.offline.plot(fig, filename=iname, auto_open=False)

    @classmethod
    def plot_line_graph(cls, title: str, xtitle: str, ytitle: str, data, iname: str, xmax: int):
        layout = cls.common_layout("group", title, ytitle, xtitle, [0, xmax])

        fig = go.Figure(data=data, layout=layout)
        py.offline.plot(fig, filename=iname, auto_open=False)

    def arrange_data(self):
        try:
            self.dataset[self.key]
        except KeyError:
            pass
        else:
            for ii, ki in enumerate(self.dataset[self.key]["seller"]):
                if ki in self.trade_history.keys():
                    self.trade_history[ki] += abs(self.dataset[self.key]["energy [kWh]"][ii])
                else:
                    self.trade_history[ki] = abs(self.dataset[self.key]["energy [kWh]"][ii])

    def plot_pie_chart(self, title, filename):
        fig = {
            "data": [
                {
                    "values": list(),
                    "labels": list(),
                    "type": "pie"
                }],
            "layout": {
                "title": title,
                "font": {"size": 16
                         }
            }
        }
        for key, value in self.trade_history.items():
            fig["data"][0]["values"].append(value)
            fig["data"][0]["labels"].append(key)

        py.offline.plot(fig, filename=filename, auto_open=False)

    @classmethod
    def _plot_time_series_line(cls, device_dict, var_name):
        color = _get_color(var_name, 1)
        fill_color = _get_color(var_name, 0.4)
        x, y, y_lower, y_upper = cls.prepare_input(device_dict, var_name)
        yaxis = "y"
        connectgaps = True
        line = dict(color=color,
                    width=0.8)
        time_series = go.Scatter(
            x=x,
            y=y,
            line=line,
            mode='lines+markers',
            marker=dict(size=5),
            name=var_name,
            showlegend=True,
            hoverinfo='none',
            fill=None,
            xaxis="x",
            yaxis=yaxis,
            connectgaps=connectgaps
        )
        longterm_max_hover = go.Scatter(
            x=x,
            y=y_upper,
            fill=None,
            fillcolor=fill_color,
            line=dict(color='rgba(255,255,255,0)'),
            name=f"max {var_name}",
            showlegend=False,
            hoverinfo='y+name',
            xaxis="x",
            yaxis=yaxis,
            connectgaps=connectgaps
        )
        longterm_min_hover = go.Scatter(
            x=x,
            y=y_lower,
            fill=None,
            fillcolor=fill_color,
            line=dict(color='rgba(255,255,255,0)'),
            name=f"min {var_name}",
            showlegend=False,
            hoverinfo='y+name',
            xaxis="x",
            yaxis=yaxis,
            connectgaps=connectgaps
        )
        shade = go.Scatter(
            x=x,
            y=y_upper,
            fill='tonexty',
            fillcolor=fill_color,
            line=dict(color='rgba(255,255,255,0)'),
            name=f"minmax {var_name}",
            showlegend=True,
            hoverinfo='none',
            xaxis="x",
            yaxis=yaxis,
            connectgaps=connectgaps
        )
        hoverinfo_x = go.Scatter(
            x=x,
            y=y_upper,
            mode="none",
            hoverinfo="x",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis
        )
        return [longterm_min_hover, shade, time_series, longterm_max_hover, hoverinfo_x]

    @classmethod
    def _plot_time_series_bar_storage(cls, device_dict, var_name):
        color = _get_color(var_name, 1)
        fill_color = _get_color(var_name, 0.4)
        x, y, y_lower, y_upper = cls.prepare_input(device_dict, var_name)
        yaxis = "y2"
        time_series = go.Bar(
            x=x,
            y=y,
            marker=dict(
                color=fill_color,
                line=dict(
                    color=color,
                    width=1.,
                )
            ),
            name=var_name,
            showlegend=True,
            hoverinfo='none',
            xaxis="x",
            yaxis=yaxis,
        )

        return [time_series] + cls._hoverinfo_trace(x, y_lower, y_upper, yaxis)

    @classmethod
    def _plot_time_series_bar_pv_load(cls, device_dict, var1_name, var2_name, invert_y=False):
        color1 = _get_color(var1_name, 1)
        fill_color1 = _get_color(var1_name, 0.4)
        color2 = _get_color(var2_name, 1)
        fill_color2 = _get_color(var2_name, 1)
        x1, y1, y_lower1, y_upper1 = cls.prepare_input(device_dict, var1_name)
        x2, y2, y_lower2, y_upper2 = cls.prepare_input(device_dict, var2_name, invert_y)

        yaxis = "y2"
        time_series1 = go.Bar(
            x=x1,
            y=y1,
            marker=dict(
                color=fill_color1,
                line=dict(
                    color=color1,
                    width=1.,
                )
            ),
            name=var1_name,
            showlegend=True,
            hoverinfo='y+name',
            xaxis="x",
            yaxis=yaxis,
        )
        time_series2 = go.Bar(
            x=x2,
            y=y2,
            marker=dict(
                color=fill_color2,
                line=dict(
                    color=color2,
                    width=1.,
                )
            ),
            name=var2_name,
            showlegend=True,
            hoverinfo='y+name',
            xaxis="x",
            yaxis=yaxis,
        )

        return [time_series1, time_series2] + cls._hoverinfo_trace(x1, y_lower1, y_upper1, yaxis,
                                                                   only_x=True)

    @classmethod
    def _hoverinfo_trace(cls, x, y_lower, y_upper, yaxis, only_x=False):
        hoverinfo_max = go.Scatter(
            x=x,
            y=y_upper,
            mode="none",
            name="longterm_max",
            hoverinfo="y+name",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis
        )
        hoverinfo_min = go.Scatter(
            x=x,
            y=y_lower,
            mode="none",
            name="longterm_min",
            hoverinfo="y+name",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis
        )
        hoverinfo_x = go.Scatter(
            x=x,
            y=y_upper,
            mode="none",
            hoverinfo="x",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis
        )
        if only_x:
            return [hoverinfo_x]
        else:
            return [hoverinfo_max, hoverinfo_min, hoverinfo_x]

    @classmethod
    def _plot_time_series_price_candle(cls, device_dict, var_name):

        time_list, y, y_lower, y_upper = cls.prepare_input(device_dict, var_name)
        x = []
        y_min = []
        y_max = []
        yy_lower = []
        yy_upper = []
        for ii in range(len(y)):
            if y[ii] is not None:
                x.append(time_list[ii])
                y_min.append(limit_float_precision(min(y[ii])))
                y_max.append(limit_float_precision(max(y[ii])))
                yy_lower.append(limit_float_precision(y_lower[ii]))
                yy_upper.append(limit_float_precision(y_upper[ii]))

        yaxis = "y3"
        color = _get_color(var_name, 1)

        candle_stick = go.Candlestick(x=x,
                                      open=y_min,
                                      high=yy_upper,
                                      low=yy_lower,
                                      close=y_max,
                                      yaxis=yaxis,
                                      xaxis="x",
                                      hoverinfo="none",
                                      name=var_name,
                                      increasing=dict(line=dict(color=color)),
                                      decreasing=dict(line=dict(color=color)),
                                      )
        hoverinfo_max = go.Scatter(
            x=x,
            y=y_max,
            mode="none",
            name="max",
            hoverinfo="y+name",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis
        )
        hoverinfo_min = go.Scatter(
            x=x,
            y=y_min,
            mode="none",
            name="min",
            hoverinfo="y+name",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis
        )

        return [candle_stick, hoverinfo_max, hoverinfo_min] + cls._hoverinfo_trace(x, yy_lower,
                                                                                   yy_upper, yaxis)

    @classmethod
    def prepare_input(cls, device_dict, var_name, invert_y=False):
        x = list(device_dict[var_name].keys())
        y = list(device_dict[var_name].values())
        y_lower = list(device_dict["min_" + var_name].values())
        y_upper = list(device_dict["max_" + var_name].values())
        if invert_y:
            return x, _invert(y), _invert(y_lower), _invert(y_upper)
        else:
            return x, y, y_lower, y_upper

    @classmethod
    def _get_y2_range(cls, device_dict, var_name, zero=True):
        y = list(device_dict[var_name].values())
        ddd = max([abs(x) for x in y if x is not None])
        mma = ddd + ddd * 0.1
        if zero:
            return [0, abs(mma)]
        else:
            return [-mma, mma]

    @classmethod
    def _plot_device_profile(cls, device_dict, device_name, output_file, device_strategy):
        data = []
        # Trade Price graph (y3):
        data += cls._plot_time_series_price_candle(device_dict, "trade_price_eur")
        # Traded energy graph (y2):
        if isinstance(device_strategy, StorageStrategy):
            key = "soc_history_%"
            data += cls._plot_time_series_bar_storage(device_dict, "trade_energy_kWh")
            y2_range = cls._get_y2_range(device_dict, "trade_energy_kWh", zero=False)
            y2axis_title = "Bought/Sold [kWh]"
        elif isinstance(device_strategy, LoadHoursStrategy):
            key = "load_profile_kWh"
            data += cls._plot_time_series_bar_pv_load(device_dict, key, "trade_energy_kWh")
            y2axis_title = "Demand/Traded [kWh]"
            y2_range = cls._get_y2_range(device_dict, "load_profile_kWh")
        elif isinstance(device_strategy, PVStrategy):
            key = "pv_production_kWh"
            data += cls._plot_time_series_bar_pv_load(device_dict, key,
                                                      "trade_energy_kWh", invert_y=True)
            y2_range = cls._get_y2_range(device_dict, key)
            y2axis_title = "Supply/Traded [kWh]"
        else:
            return
        # SOC, load_curve, pv production graph (y):
        data += cls._plot_time_series_line(device_dict, key)
        yaxis_title = DEVICE_YAXIS[key]

        layout = cls._device_plot_layout("overlay", f"{device_name}", 'Time',
                                         yaxis_title, y2axis_title, y2_range)
        fig = go.Figure(data=data, layout=layout)
        py.offline.plot(fig, filename=output_file, auto_open=False)

    @staticmethod
    def _device_plot_layout(barmode, title, xtitle, yaxis_title, y2axis_title, y2_range):
        return go.Layout(
            autosize=False,
            width=1200,
            height=700,
            barmode=barmode,
            title=title,
            xaxis=dict(
                title=xtitle,
                showgrid=True,
                anchor="y3",
                rangeslider=dict(visible=True,
                                 thickness=0.075,
                                 bgcolor='rgba(100,100,100,0.3)'
                                 )
            ),
            yaxis=dict(
                title=yaxis_title,
                side='left',
                showgrid=True,
                domain=[0.66, 1],
                rangemode='tozero',
                autorange=True
            ),
            yaxis2=dict(
                title=y2axis_title,
                side='right',
                range=y2_range,
                showgrid=True,
                domain=[0.33, 0.66],
                autorange=False
            ),
            yaxis3=dict(
                title='Energy rate [EUR/kWh]',
                domain=[0.0, 0.33],
                side='left',
                showgrid=True,
                rangemode='tozero',
                autorange=True
            ),
            font=dict(
                size=12
            ),
            showlegend=True,
            legend=dict(x=1.1, y=1)
        )
