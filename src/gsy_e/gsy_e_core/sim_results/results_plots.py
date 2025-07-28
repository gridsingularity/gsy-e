import operator
import os
from collections import namedtuple
from copy import deepcopy
from functools import reduce  # forward compatibility for Python 3
from typing import Dict, Tuple, List, Mapping, TYPE_CHECKING

import pandas as pd
import plotly as py
import plotly.graph_objs as go
from gsy_framework.constants_limits import ConstSettings, GlobalConfig, DATE_TIME_FORMAT
from gsy_framework.data_classes import Clearing
from gsy_framework.utils import mkdir_from_str, generate_market_slot_list
from pendulum import DateTime
from plotly.subplots import make_subplots
from slugify import slugify
from sortedcontainers import SortedDict

from gsy_e.data_classes import PlotDescription
from gsy_e.gsy_e_core.sim_results.file_export_endpoints import is_heatpump_with_tanks
from gsy_e.gsy_e_core.sim_results.plotly_graph import PlotlyGraph
from gsy_e.gsy_e_core.util import round_floats_for_ui
from gsy_e.models.area import Area
from gsy_e.models.strategy.state import ESSEnergyOrigin
from gsy_e.models.strategy.storage import StorageStrategy

if TYPE_CHECKING:
    from gsy_e.gsy_e_core.sim_results.file_export_endpoints import FileExportEndpoints
    from gsy_e.gsy_e_core.sim_results.endpoint_buffer import SimulationEndpointBuffer

ENERGY_BUYER_SIGN_PLOTS = 1
ENERGY_SELLER_SIGN_PLOTS = -1 * ENERGY_BUYER_SIGN_PLOTS

SlotDataRange = namedtuple("SlotDataRange", ("start", "end"))


class PlotUnmatchedLoads:
    """Plot the unmatched loads of the whole grid tree."""

    def __init__(self, root_area, file_stats_endpoint, plot_dir):
        self._root_area = root_area
        self._file_stats_endpoint = file_stats_endpoint
        self._plot_dir = plot_dir

    def plot(self):
        """
        Plot unmatched loads of all loads in the configuration into one plot
        """
        root_name = self._root_area.slug
        plot_desc = PlotDescription(
            data=[],
            barmode="stack",
            xtitle="Time",
            ytitle="Energy (kWh)",
            title=f"Unmatched Loads for all devices in {root_name}",
        )
        unmatched_key = "deficit [kWh]"
        load_list = [
            child_key
            for child_key in self._file_stats_endpoint.plot_stats.keys()
            if unmatched_key in self._file_stats_endpoint.plot_stats[child_key].keys()
        ]

        for li in load_list:
            graph_obj = PlotlyGraph(self._file_stats_endpoint.plot_stats[li], unmatched_key)
            if sum(graph_obj.dataset[unmatched_key]) < 1e-10:
                continue
            graph_obj.graph_value()
            data_obj = go.Bar(
                x=list(graph_obj.umHours.keys()), y=list(graph_obj.umHours.values()), name=li
            )
            plot_desc.data.append(data_obj)
        if len(plot_desc.data) == 0:
            return
        plot_dir = os.path.join(self._plot_dir)
        mkdir_from_str(plot_dir)
        output_file = os.path.join(plot_dir, f"unmatched_loads_{root_name}.html")
        PlotlyGraph.plot_bar_graph(plot_desc, output_file)


class PlotEnergyProfile:
    """Plot the energy profile of all areas."""

    def __init__(self, endpoint_buffer: "SimulationEndpointBuffer", plot_dir: str):
        self._endpoint_buffer = endpoint_buffer
        self._plot_dir = plot_dir

    def plot(self, area: Area, directory: str = None) -> None:
        """Plot the energy profile of areas (not devices)."""
        if not directory:
            directory = self._plot_dir
        energy_profile = self._endpoint_buffer.results_handler.trade_profile_plot_results

        new_subdir = os.path.join(directory, area.slug)
        self._plot_energy_profile(new_subdir, area.name, energy_profile)
        for child in area.children:
            if child.children:
                self.plot(child, new_subdir)

    def _plot_energy_profile(self, subdir: str, market_name: str, energy_profile) -> None:
        """
        Plots history of energy trades
        """
        if market_name not in energy_profile:
            return

        plot_desc = PlotDescription(
            data=[],
            barmode="relative",
            xtitle="Time",
            ytitle="Energy [kWh]",
            title=f"Energy Trade Profile of {market_name}",
        )
        key = "energy"
        plot_desc.data.extend(
            self._plot_energy_graph(
                energy_profile, market_name, "sold_energy_lists", "seller", key
            )
        )
        plot_desc.data.extend(
            self._plot_energy_graph(
                energy_profile, market_name, "bought_energy_lists", "buyer", key
            )
        )
        if len(plot_desc.data) == 0:
            return
        if all(len(da.y) == 0 for da in plot_desc.data):
            return
        plot_dir = os.path.join(self._plot_dir, subdir)
        mkdir_from_str(plot_dir)
        output_file = os.path.join(plot_dir, f"energy_profile_{market_name}.html")
        PlotlyGraph.plot_bar_graph(plot_desc, output_file)

    @staticmethod
    def _plot_energy_graph(trades, market_name, agent, agent_label, key):
        if agent_label == "seller":
            scale_value = ENERGY_SELLER_SIGN_PLOTS
        elif agent_label == "buyer":
            scale_value = ENERGY_BUYER_SIGN_PLOTS
        else:
            raise AssertionError(
                "_plot_energy_graph agent_label should be either " "'seller' or 'buyer'"
            )
        internal_data = []
        for trader in trades[market_name][agent].keys():
            graph_obj = PlotlyGraph(trades[market_name][agent][trader], key)
            graph_obj.graph_value(scale_value=scale_value)
            data_obj = go.Bar(
                x=list(graph_obj.umHours.keys()),
                y=list(graph_obj.umHours.values()),
                name=trader + "-" + agent_label,
            )
            internal_data.append(data_obj)
        return internal_data


class PlotDeviceStats:
    """Plot the statistics of all devices."""

    def __init__(self, endpoint_buffer: "SimulationEndpointBuffer", plot_dir: str):
        self._endpoint_buffer = endpoint_buffer
        self._plot_dir = plot_dir

    def plot(self, area: Area, node_address_list: list) -> None:
        """
        Wrapper for _plot_device_stats
        """
        new_node_address_list = node_address_list + [area.name]
        for child in area.children:
            if child.children:
                self.plot(child, new_node_address_list)
            else:
                address_list = new_node_address_list + [child.name]
                self._plot_device_stats(address_list, child.strategy)

    @staticmethod
    def _get_from_dict(data_dict: Dict, map_list: List) -> Mapping:
        """Get nested data from a dict by following a path provided by a list of keys."""
        try:
            return reduce(operator.getitem, map_list, data_dict)
        except KeyError:
            return {}

    def _plot_device_stats(self, address_list: list, device_strategy):
        """Plot device graphs."""
        # Dont use the root area name for address list:
        device_address_list = address_list[1::]

        device_name = device_address_list[-1].replace(" ", "_")
        device_stats = self._endpoint_buffer.results_handler.all_raw_results["device_statistics"]
        device_dict = self._get_from_dict(device_stats, device_address_list)
        # converting address_list into plot_dir by slugifying the members
        plot_dir = os.path.join(
            self._plot_dir, "/".join([slugify(node).lower() for node in address_list][0:-1])
        )
        mkdir_from_str(plot_dir)
        output_file = os.path.join(plot_dir, f"device_profile_{device_name}.html")
        PlotlyGraph.plot_device_profile(device_dict, device_name, output_file, device_strategy)


class PlotESSSOCHistory:
    """Plot the SOC history of the Storage"""

    def __init__(self, file_stats_endpoint, plot_dir):
        self._file_stats_endpoint = file_stats_endpoint
        self._plot_dir = plot_dir

    def plot(self, area, subdir):
        """
        Wrapper for _plot_ess_soc_history.
        """

        storage_key = "charge [%]"
        new_subdir = os.path.join(subdir, area.slug)
        storage_list = [
            child.slug
            for child in area.children
            if storage_key in self._file_stats_endpoint.plot_stats[child.slug].keys()
        ]
        if not storage_list:
            self._plot_ess_soc_history(storage_list, new_subdir, area.slug)
        for child in area.children:
            if child.children:
                self.plot(child, new_subdir)

    def _plot_ess_soc_history(self, storage_list: list, subdir: str, root_name: str):
        """
        Plots ess soc for each knot in the hierarchy
        """
        plot_desc = PlotDescription(
            data=[],
            barmode="relative",
            xtitle="Time",
            ytitle="Charge [%]",
            title=f"ESS SOC ({root_name})",
        )

        storage_key = "charge [%]"

        for si in storage_list:
            graph_obj = PlotlyGraph(self._file_stats_endpoint.plot_stats[si], storage_key)
            graph_obj.graph_value()
            data_obj = go.Scatter(
                x=list(graph_obj.umHours.keys()), y=list(graph_obj.umHours.values()), name=si
            )
            plot_desc.data.append(data_obj)
        if len(plot_desc.data) == 0:
            return
        plot_dir = os.path.join(self._plot_dir, subdir)
        mkdir_from_str(plot_dir)
        output_file = os.path.join(plot_dir, f"ess_soc_history_{root_name}.html")
        PlotlyGraph.plot_bar_graph(plot_desc, output_file)


class PlotESSEnergyTrace:
    """Plot the storage of the energy trace"""

    def __init__(self, plot_dir):
        self._plot_dir = plot_dir

    def plot(self, area, subdir):
        """
        Wrapper for _plot.
        """

        new_subdir = os.path.join(subdir, area.slug)
        storage_list = [
            child for child in area.children if isinstance(child.strategy, StorageStrategy)
        ]
        for element in storage_list:
            self._plot(element.strategy.state.time_series_ess_share, new_subdir, area.slug)
        for child in area.children:
            if child.children:
                self.plot(child, new_subdir)

    def _plot(self, energy: dict, subdir: str, root_name: str):
        """
        Plots ess energy trace for each knot in the hierarchy
        """
        plot_desc = PlotDescription(
            data=[],
            barmode="stack",
            xtitle="Time",
            ytitle="Energy [kWh]",
            title=f"ESS ENERGY SHARE ({root_name})",
        )

        temp = {
            ESSEnergyOrigin.UNKNOWN: {slot: 0.0 for slot in generate_market_slot_list()},
            ESSEnergyOrigin.LOCAL: {slot: 0.0 for slot in generate_market_slot_list()},
            ESSEnergyOrigin.EXTERNAL: {slot: 0.0 for slot in generate_market_slot_list()},
        }

        for time, energy_info in energy.items():
            temp[ESSEnergyOrigin.EXTERNAL][time] = energy_info[ESSEnergyOrigin.EXTERNAL]
            temp[ESSEnergyOrigin.LOCAL][time] = energy_info[ESSEnergyOrigin.LOCAL]
            temp[ESSEnergyOrigin.UNKNOWN][time] = energy_info[ESSEnergyOrigin.UNKNOWN]
        for energy_type in [
            ESSEnergyOrigin.EXTERNAL,
            ESSEnergyOrigin.LOCAL,
            ESSEnergyOrigin.UNKNOWN,
        ]:
            data_obj = go.Bar(
                x=list(temp[energy_type].keys()),
                y=list(temp[energy_type].values()),
                name=f"{energy_type}",
            )
            plot_desc.data.append(data_obj)
        if len(plot_desc.data) == 0:
            return
        plot_dir = os.path.join(self._plot_dir, subdir)
        mkdir_from_str(plot_dir)
        output_file = os.path.join(plot_dir, f"ess_energy_share_{root_name}.html")
        PlotlyGraph.plot_bar_graph(plot_desc, output_file)


class PlotSupplyDemandCurve:
    """Plot the supply demand curve of the asset"""

    def __init__(self, file_stats_endpoint: "FileExportEndpoints", plot_dir: str):
        self._file_stats_endpoint = file_stats_endpoint
        self._plot_dir = plot_dir

    def plot(self, area: Area, subdir: str):
        """
        Wrapper for _plot_supply_demand_curve
        """
        new_subdir = os.path.join(subdir, area.slug)
        self._plot_supply_demand_curve(new_subdir, area)
        for child in area.children:
            if child.children:
                self.plot(child, new_subdir)

    def _plot_supply_demand_curve(self, subdir: str, area: Area):
        if area.slug not in self._file_stats_endpoint.clearing:
            return
        for market_slot, clearing in self._file_stats_endpoint.clearing[area.slug].items():
            data = []
            xmax = 0
            for time_slot, supply_curve in self._file_stats_endpoint.cumulative_offers[area.slug][
                market_slot
            ].items():
                data.append(self._render_supply_demand_curve(supply_curve, time_slot, True))
            for time_slot, demand_curve in self._file_stats_endpoint.cumulative_bids[area.slug][
                market_slot
            ].items():
                data.append(self._render_supply_demand_curve(demand_curve, time_slot, False))

            if len(data) == 0:
                continue

            for time_slot, clearing_point in clearing.items():
                if isinstance(clearing_point, Clearing) and clearing_point.energy > 0:
                    data_obj = go.Scatter(
                        x=[0, clearing_point.energy],
                        y=[clearing_point.rate, clearing_point.rate],
                        mode="lines+markers",
                        line=dict(width=5),
                        name=time_slot.format(DATE_TIME_FORMAT) + " Clearing-Rate",
                    )
                    data.append(data_obj)
                    data_obj = go.Scatter(
                        x=[clearing_point.energy, clearing_point.energy],
                        y=[0, clearing_point.rate],
                        mode="lines+markers",
                        line=dict(width=5),
                        name=time_slot.format(DATE_TIME_FORMAT) + " Clearing-Energy",
                    )
                    data.append(data_obj)
                    xmax = max(xmax, clearing_point.energy) * 3

            plot_dir = os.path.join(self._plot_dir, subdir, "mcp")
            mkdir_from_str(plot_dir)
            output_file = os.path.join(plot_dir, f"supply_demand_{market_slot}.html")
            plot_desc = PlotDescription(
                data=data,
                barmode="group",
                xtitle="Energy (kWh)",
                ytitle="Rate (ct./kWh)",
                title="supply_demand_curve",
            )
            PlotlyGraph.plot_line_graph(plot_desc, output_file, xmax)

    @classmethod
    def _render_supply_demand_curve(
        cls, dataset: Dict, time: DateTime, supply: bool
    ) -> go.Scatter:
        rate, energy = cls._calc_supply_demand_curve(dataset, supply=supply)
        name = str(time) + "-" + ("supply" if supply else "demand")
        data_obj = go.Scatter(x=energy, y=rate, mode="lines", name=name)
        return data_obj

    @staticmethod
    def _calc_supply_demand_curve(dataset: Dict, supply: bool = True) -> Tuple[List, List]:
        sort_values = SortedDict(dataset)
        if supply:
            rate = list(sort_values.keys())
            energy = list(sort_values.values())
        else:
            rate = list(reversed(sort_values.keys()))
            energy = list(reversed(sort_values.values()))

        cond_rate = []
        cond_energy = []

        for i, energy_for_rate in enumerate(energy):

            if i == 0:
                cond_rate.append(rate[0])
                cond_energy.append(0)
                cond_rate.append(rate[0])
                cond_energy.append(energy_for_rate)
            else:
                if energy[i - 1] == energy[i] and supply:
                    continue
                cond_rate.append(rate[i])
                cond_energy.append(energy[i - 1])
                cond_energy.append(energy[i])
                cond_rate.append(rate[i])
        return cond_rate, cond_energy


class PlotAverageTradePrice:
    """Plot the average trade price of the market"""

    def __init__(self, file_stats_endpoint, plot_dir):
        self._file_stats_endpoint = file_stats_endpoint
        self._plot_dir = plot_dir

    def plot(self, area, subdir):
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
                self.plot(child, new_subdir)

    def _plot_avg_trade_price(self, area_list: list, subdir: str):
        """
        Plots average trade for the specified level of the hierarchy
        """
        plot_desc = PlotDescription(
            data=[],
            barmode="stack",
            xtitle="Time",
            ytitle="Rate [ct./kWh]",
            title=f"Average Trade Price {area_list[0]}",
        )
        key = "avg trade rate [ct./kWh]"
        for area_name in area_list:
            plot_desc.data.append(
                self._plot_avg_trade_graph(
                    self._file_stats_endpoint.plot_stats, area_name, key, area_name
                )
            )
            if (
                ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET
                and self._file_stats_endpoint.plot_balancing_stats[area_name.lower()] is not None
            ):
                area_name_balancing = area_name.lower() + "-demand-balancing-trades"
                plot_desc.data.append(
                    self._plot_avg_trade_graph(
                        self._file_stats_endpoint.plot_balancing_stats,
                        area_name,
                        "avg demand balancing trade rate [ct./kWh]",
                        area_name_balancing,
                    )
                )
                area_name_balancing = area_name.lower() + "-supply-balancing-trades"
                plot_desc.data.append(
                    self._plot_avg_trade_graph(
                        self._file_stats_endpoint.plot_balancing_stats,
                        area_name,
                        "avg supply balancing trade rate [ct./kWh]",
                        area_name_balancing,
                    )
                )

        if all(len(da.y) == 0 for da in plot_desc.data):
            return
        plot_dir = os.path.join(self._plot_dir, subdir)
        mkdir_from_str(plot_dir)
        output_file = os.path.join(plot_dir, f"average_trade_price_{area_list[0]}.html")
        PlotlyGraph.plot_bar_graph(plot_desc, output_file)

    @staticmethod
    def _plot_avg_trade_graph(stats, area_name, key, label):
        graph_obj = PlotlyGraph(stats[area_name.lower()], key)
        graph_obj.graph_value()
        data_obj = go.Scatter(
            x=list(graph_obj.umHours.keys()),
            y=list(graph_obj.umHours.values()),
            name=label.lower(),
        )
        return data_obj


class PlotOrderInfo:
    """Create plot for the order high resolution information"""

    def __init__(self, endpoint_buffer: "SimulationEndpointBuffer"):
        self._endpoint_buffer = endpoint_buffer

    def plot_per_area_per_market_slot(self, area: "Area", plot_dir: str):
        """
        Wrapper for _plot_per_area_per_market_slot.
        """
        new_sub_dir = os.path.join(plot_dir, area.slug)
        mkdir_from_str(new_sub_dir)
        self._plot_per_area_per_market_slot(area, new_sub_dir)

        for child in area.children:
            if not child.children:
                continue
            self.plot_per_area_per_market_slot(child, new_sub_dir)

    def _plot_per_area_per_market_slot(self, area: Area, plot_dir: str):
        """
        Plots order stats for each knot in the hierarchy per market_slot
        """
        area_stats = self._endpoint_buffer.offer_bid_trade_hr.state[area.name]
        market_slot_data_mapping = {}
        fig = go.Figure()

        for index, markets in enumerate(area_stats.values()):
            start = len(fig.data)
            for tick_time, info_dicts in markets.items():
                self._generate_tooltip_data_for_tick(info_dicts)
                self._plot_tooltip_for_tick(info_dicts, fig, tick_time)

            market_slot_data_mapping[index] = SlotDataRange(start, len(fig.data))
        PlotlyGraph.plot_slider_graph(fig, plot_dir, area.name, market_slot_data_mapping)

    @staticmethod
    def _generate_tooltip_data_for_tick(info_dicts: Dict):
        for info_dict in info_dicts:
            if info_dict["tag"] == "bid":
                tool_tip = (
                    f"{info_dict['buyer_origin']} "
                    f"Bid ({info_dict['energy']} kWh @ "
                    f"{round_floats_for_ui(info_dict['rate'])} € cents / kWh)"
                )
                info_dict.update({"tool_tip": tool_tip})
            elif info_dict["tag"] == "offer":
                tool_tip = (
                    f"{info_dict['seller_origin']} "
                    f"Offer({info_dict['energy']} kWh @ "
                    f"{round_floats_for_ui(info_dict['rate'])} € cents / kWh)"
                )
                info_dict.update({"tool_tip": tool_tip})
            elif info_dict["tag"] == "trade":
                tool_tip = (
                    f"Trade: {info_dict['seller_origin']} --> "
                    f"{info_dict['buyer_origin']} ({info_dict['energy']} kWh @ "
                    f"{round_floats_for_ui(info_dict['rate'])} € / kWh)"
                )
                info_dict.update({"tool_tip": tool_tip})

    @staticmethod
    def _plot_tooltip_for_tick(info_dicts: Dict, fig: go.Figure, tick_time: DateTime):
        for info_dict in info_dicts:
            size = 5 if info_dict["tag"] in ["offer", "bid"] else 10
            all_info_dicts = list(
                [info_dict, *[i for i in info_dicts if i["rate"] == info_dict["rate"]]]
            )
            # Removes duplicate dicts from a list of dicts
            all_info_dicts = [dict(t) for t in {tuple(sorted(d.items())) for d in all_info_dicts}]
            all_info_dicts.sort(key=lambda e: e["tool_tip"])
            tooltip_text = "<br />".join(map(lambda e: e["tool_tip"], all_info_dicts))
            fig.add_trace(
                go.Scatter(
                    x=[tick_time],
                    y=[info_dict["rate"]],
                    text=tooltip_text,
                    hoverinfo="text",
                    marker=dict(size=size, color=all_info_dicts[0]["color"]),
                    visible=False,
                )
            )


class PlotEnergyTradeProfileHR:
    """Plots the high resolution energy trade profile"""

    def __init__(self, endpoint_buffer: "SimulationEndpointBuffer", plot_dir: str):
        self._endpoint_buffer = endpoint_buffer
        self._plot_dir = plot_dir

    def plot(self, area: Area, subdir: str):
        """
        Wrapper for _plot_energy_profile_hr
        """
        new_subdir = os.path.join(subdir, area.slug)
        self._plot_energy_profile_hr(area, new_subdir)
        for child in area.children:
            if child.children:
                self.plot(child, new_subdir)

    def _plot_energy_profile_hr(self, area: Area, subdir: str):
        """
        Plots history of energy trades plotted for each market_slot
        """
        market_name = area.name
        plot_desc = PlotDescription(
            data=[],
            barmode="relative",
            xtitle="Time",
            ytitle="Energy [kWh]",
            title=f"High Resolution Energy Trade Profile of {market_name}",
        )

        area_stats = self._endpoint_buffer.offer_bid_trade_hr.state[area.name]
        plot_dir = os.path.join(self._plot_dir, subdir, "energy_profile_hr")
        mkdir_from_str(plot_dir)
        for market_slot, data in area_stats.items():
            plot_data = self.get_plotly_graph_dataset(data, market_slot)
            if len(plot_data) > 0:
                market_slot_str = market_slot.format(DATE_TIME_FORMAT)
                output_file = os.path.join(
                    plot_dir, f"energy_profile_hr_{market_name}_{market_slot_str}.html"
                )
                time_range = [
                    market_slot - GlobalConfig.tick_length,
                    market_slot + GlobalConfig.slot_length + GlobalConfig.tick_length,
                ]
                PlotlyGraph.plot_bar_graph(plot_desc, output_file, time_range=time_range)

    def get_plotly_graph_dataset(self, market_trades: Dict, market_slot: DateTime) -> List:
        """Add plotly graph dataset"""
        plotly_dataset_list = []

        seller_dict, buyer_dict = self._accumulate_data_by_buyer_seller(market_slot, market_trades)

        # Create bar plot objects and collect them in a list
        # The widths of bars in a plotly.Bar is set in milliseconds when axis is in datetime format
        for agent, data in seller_dict.items():
            data_obj = go.Bar(
                x=data["timestamp"],
                y=data["energy"],
                width=GlobalConfig.tick_length.seconds * 1000,
                name=agent + "-seller",
            )
            plotly_dataset_list.append(data_obj)

        for agent, data in buyer_dict.items():
            data_obj = go.Bar(
                x=data["timestamp"],
                y=data["energy"],
                width=GlobalConfig.tick_length.seconds * 1000,
                name=agent + "-buyer",
            )
            plotly_dataset_list.append(data_obj)
        return plotly_dataset_list

    @staticmethod
    def _accumulate_data_by_buyer_seller(
        market_slot: DateTime, market_trades: Dict
    ) -> Tuple[Dict, Dict]:
        # accumulate data by buyer and seller:
        seller_dict = {}
        buyer_dict = {}
        # This zero point is needed to make plotly also plot the first data point:
        zero_point_dict = {"timestamp": [market_slot - GlobalConfig.tick_length], "energy": [0.0]}

        for market_slot_time, market_slot_trades in market_trades.items():
            for trade in market_slot_trades:
                if trade["tag"] == "trade":
                    trade_time = market_slot_time
                    seller = trade["seller_origin"]
                    buyer = trade["buyer_origin"]
                    energy = trade["energy"]
                    if seller not in seller_dict:
                        seller_dict[seller] = deepcopy(zero_point_dict)
                    if buyer not in buyer_dict:
                        buyer_dict[buyer] = deepcopy(zero_point_dict)
                    seller_dict[seller]["timestamp"].append(trade_time)
                    seller_dict[seller]["energy"].append(energy * ENERGY_SELLER_SIGN_PLOTS)
                    buyer_dict[buyer]["timestamp"].append(trade_time)
                    buyer_dict[buyer]["energy"].append(energy * ENERGY_BUYER_SIGN_PLOTS)

        return seller_dict, buyer_dict


class PlotHPPhysicalStats:
    """Plots the high resolution energy trade profile"""

    def plot(self, area: Area, subdir: str):
        """
        Wrapper for _plot_energy_profile_hr
        """
        new_subdir = os.path.join(subdir, area.slug)
        self._plot_hp_physical_stats(area, new_subdir)
        for child in area.children:
            if child.children:
                self.plot(child, new_subdir)

    @staticmethod
    def _get_source_csv_filename(sub_dir: str, device_name: str):
        directory = sub_dir.replace("plot/", "")
        filename = f"{slugify(device_name).lower()}_heat_pump.csv"
        return os.path.join(directory, filename)

    @staticmethod
    def _get_out_filename(sub_dir: str, device_name: str):
        return os.path.join(sub_dir, f"hp_physical_stats_{slugify(device_name).lower()}.html")

    def _plot_hp_physical_stats(self, area, sub_dir):
        for device in area.children:
            if not is_heatpump_with_tanks(device):
                continue
            self._plot_graph(
                self._get_source_csv_filename(sub_dir, device.name),
                self._get_out_filename(sub_dir, device.name),
            )

    @staticmethod
    def _plot_graph(source_file: str, out_file: str):
        data = pd.read_csv(source_file)

        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            subplot_titles=(
                "Average SOC [%]",
                "Coefficient of Performance",
                "Condenser Temperature [°C]",
            ),
        )

        fig.add_trace(
            go.Scatter(x=data["slot"], y=data["average SOC"], name="Average SOC [%]"), row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=data["slot"], y=data["COP"], name="Coefficient of Performance"),
            row=2,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=data["slot"],
                y=data["condenser temperature [C]"],
                name="Condenser Temperature [°C]",
            ),
            row=3,
            col=1,
        )

        fig.update_layout(height=700, width=900, hovermode="x", showlegend=False)
        fig.update_xaxes(title_text="Date", row=3, col=1)
        fig.update_yaxes(title_text="Average SOC [%]", row=1, col=1)
        fig.update_yaxes(title_text="COP", row=2, col=1)
        fig.update_yaxes(title_text="temperature [°C]", row=3, col=1)

        py.offline.plot(fig, filename=out_file, auto_open=False)
