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

import os

import pendulum
import plotly as py
import plotly.graph_objs as go

from gsy_framework.utils import limit_float_precision
from gsy_framework.constants_limits import TIME_ZONE
from gsy_e.data_classes import PlotDescription
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.finite_power_plant import FinitePowerPlant
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.market_maker_strategy import MarketMakerStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.smart_meter import SmartMeterStrategy
from gsy_e.models.strategy.storage import StorageStrategy
from gsy_e.models.strategy.scm.load import SCMLoadProfileStrategy, SCMLoadHoursStrategy
from gsy_e.models.strategy.scm.pv import SCMPVUserProfile
from gsy_e.models.strategy.scm.smart_meter import SCMSmartMeterStrategy
from gsy_e.models.strategy.heat_pump import HeatPumpStrategy

green = "rgba(20,150,20, alpha)"
purple = "rgba(156, 110, 177, alpha)"
blue = "rgba(0,0,200,alpha)"

DEVICE_PLOT_COLORS = {
    "trade_energy_kWh": purple,
    "sold_trade_energy_kWh": purple,
    "bought_trade_energy_kWh": purple,
    "trade_price_eur": blue,
}

DEVICE_YAXIS = {
    "trade_energy_kWh": "Traded [kWh]",
    "sold_trade_energy_kWh": "Supply/Traded [kWh]",
    "bought_trade_energy_kWh": "Demand/Traded [kWh]",
    "pv_production_kWh": "PV Production [kWh]",
    "energy_consumption_kWh": "Energy Consumption [kWh]",
    "storage_temp_C": "Heatpump Storage Temperature [C]",
    "energy_buffer_kWh": "Energy Buffer [kWh]",
    "production_kWh": "Power Production [kWh]",
    "load_profile_kWh": "Load Profile [kWh]",
    "smart_meter_profile_kWh": "Smart Meter Profile [kWh]",
    "soc_history_%": "State of Charge [%]",
    "trade_price_eur": "Energy Rate [EUR/kWh]",
}

OPAQUE_ALPHA = 1
TRANSPARENT_ALPHA = 0.4


def _invert(inlist: list):
    return [-1 * ll for ll in inlist]


def _get_color(key, alpha):
    return DEVICE_PLOT_COLORS.get(key, green).replace("alpha", str(alpha))


class PlotlyGraph:
    """
    Encapsulates Plotly / rendering functionality for all plots. Its methods can be reused for
    rendering different plots.
    """

    def __init__(self, dataset: dict, key: str):
        self.key = key
        self.dataset = dataset
        self.umHours = {}
        self.rate = []
        self.energy = []
        self.trade_history = {}

    @staticmethod
    def _common_layout(data_desc: PlotDescription, xrange: list, showlegend=True, hovermode="x"):
        return go.Layout(
            autosize=False,
            width=1200,
            height=700,
            barmode=data_desc.barmode,
            title=data_desc.title,
            yaxis=dict(title=data_desc.ytitle),
            xaxis=dict(title=data_desc.xtitle, range=xrange),
            font=dict(size=16),
            showlegend=showlegend,
            hovermode=hovermode,
        )

    def graph_value(self, scale_value=1):
        """
        Formats the data that will be plotted. Replaces '-' values with 0, and rounds the values to
        5 decimals floating point. Supports value scaling.
        """
        try:
            self.dataset[self.key]
        except KeyError:
            pass
        else:
            for de, _ in enumerate(self.dataset[self.key]):
                if self.dataset[self.key][de] != 0:
                    if self.dataset[self.key][de] == "-":
                        self.umHours[self.dataset["slot"][de]] = 0.0
                    else:
                        self.umHours[self.dataset["slot"][de]] = (
                            round(self.dataset[self.key][de], 5) * scale_value
                        )

    @staticmethod
    def modify_time_axis(plot_desc: PlotDescription):
        """
        Changes timezone of pendulum x-values to 'UTC' and determines the list of days
        in order to return the time_range for the plot
        """
        day_set = set()
        for di, _ in enumerate(plot_desc.data):
            time_list = plot_desc.data[di]["x"]
            for ti in time_list:
                day_set.add(
                    pendulum.datetime(ti.year, ti.month, ti.day, ti.hour, ti.minute, tz=TIME_ZONE)
                )

        day_list = sorted(list(day_set))
        if len(day_list) == 0:
            raise ValueError(f"There is no time information in plot {plot_desc.title}")

        start_time = pendulum.datetime(
            day_list[0].year,
            day_list[0].month,
            day_list[0].day,
            day_list[0].hour,
            day_list[0].minute,
            day_list[0].second,
            tz=TIME_ZONE,
        )
        end_time = pendulum.datetime(
            day_list[-1].year,
            day_list[-1].month,
            day_list[-1].day,
            day_list[-1].hour,
            day_list[-1].minute,
            day_list[-1].second,
            tz=TIME_ZONE,
        )

        return [start_time, end_time], plot_desc.data

    @classmethod
    def plot_slider_graph(cls, fig, stats_plot_dir, area_name, market_slot_data_mapping):
        """Plot order data for one area of the grid."""
        # pylint: disable=too-many-locals
        steps = []
        for i, _ in enumerate(market_slot_data_mapping):
            step = dict(
                method="update",
                args=[
                    {"visible": [False] * len(fig.data)},
                    {"title": "Slider switched to slot: " + str(i)},
                ],  # layout attribute
            )
            for k in range(market_slot_data_mapping[i].start, market_slot_data_mapping[i].end):
                step["args"][0]["visible"][k] = True  # Toggle i'th trace to "visible"
            steps.append(step)
        sliders = [
            dict(
                active=0,
                currentvalue={"prefix": "MarketSlot: "},
                pad={"t": len(market_slot_data_mapping)},
                steps=steps,
            )
        ]
        output_file = os.path.join(stats_plot_dir, "offer_bid_trade_history.html")
        barmode = "group"
        title = f"OFFER BID TRADE AREA: {area_name}"
        xtitle = "Time"
        ytitle = "Rate [€ cents / kWh]"

        fig.update_layout(
            autosize=True,
            barmode=barmode,
            width=1200,
            height=700,
            title=title,
            yaxis=dict(title=ytitle),
            xaxis=dict(title=xtitle),
            font=dict(size=16),
            showlegend=False,
            sliders=sliders,
        )

        py.offline.plot(fig, filename=output_file, auto_open=False)

    @classmethod
    def plot_bar_graph(
        cls,
        plot_desc: PlotDescription,
        iname: str,
        time_range=None,
        showlegend=True,
        hovermode="x",
    ):
        """Render bar graph, used by multiple plots."""
        # pylint: disable=too-many-arguments
        if time_range is None:
            try:
                time_range, data = cls.modify_time_axis(plot_desc)
            except ValueError:
                return

        layout = cls._common_layout(plot_desc, time_range, showlegend, hovermode=hovermode)
        fig = go.Figure(data=data, layout=layout)
        py.offline.plot(fig, filename=iname, auto_open=False)

    @classmethod
    def plot_line_graph(cls, plot_desc: PlotDescription, iname: str, xmax: int):
        """Plot line graph of supply / demand curve."""
        layout = cls._common_layout(plot_desc, [0, xmax])

        fig = go.Figure(data=plot_desc.data, layout=layout)
        py.offline.plot(fig, filename=iname, auto_open=False)

    @classmethod
    def _plot_line_time_series(cls, device_dict, var_name):
        # pylint: disable=too-many-locals
        color = _get_color(var_name, OPAQUE_ALPHA)
        fill_color = _get_color(var_name, TRANSPARENT_ALPHA)
        time, var_data, longterm_min_var_data, longterm_max_var_data = cls._prepare_input(
            device_dict, var_name
        )
        yaxis = "y3"
        connectgaps = True
        line = dict(color=color, width=0.8)
        time_series = go.Scatter(
            x=time,
            y=var_data,
            line=line,
            mode="lines+markers",
            marker=dict(size=5),
            name=var_name,
            showlegend=True,
            hoverinfo="none",
            fill=None,
            xaxis="x",
            yaxis=yaxis,
            connectgaps=connectgaps,
        )
        longterm_max_hover = go.Scatter(
            x=time,
            y=longterm_max_var_data,
            fill=None,
            fillcolor=fill_color,
            line=dict(color="rgba(255,255,255,0)"),
            name="longterm max",
            showlegend=False,
            hoverinfo="y+name",
            xaxis="x",
            yaxis=yaxis,
            connectgaps=connectgaps,
        )
        longterm_min_hover = go.Scatter(
            x=time,
            y=longterm_min_var_data,
            fill=None,
            fillcolor=fill_color,
            line=dict(color="rgba(255,255,255,0)"),
            name="longterm min",
            showlegend=False,
            hoverinfo="y+name",
            xaxis="x",
            yaxis=yaxis,
            connectgaps=connectgaps,
        )
        shade = go.Scatter(
            x=time,
            y=longterm_max_var_data,
            fill="tonexty",
            fillcolor=fill_color,
            line=dict(color="rgba(255,255,255,0)"),
            name=f"minmax {var_name}",
            showlegend=True,
            hoverinfo="none",
            xaxis="x",
            yaxis=yaxis,
            connectgaps=connectgaps,
        )
        hoverinfo_time = go.Scatter(
            x=time,
            y=longterm_max_var_data,
            mode="none",
            hoverinfo="x",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis,
        )

        # it is not possible to use cls._hoverinfo here because the order matters here:
        return [longterm_min_hover, shade, time_series, longterm_max_hover, hoverinfo_time]

    @classmethod
    def _plot_bar_time_series_traded(
        cls, device_dict, traded_varname, yaxis, expected_varname=None, invert_y=False
    ):
        # pylint: disable=too-many-locals,too-many-arguments
        color_traded = _get_color(traded_varname, OPAQUE_ALPHA)
        fill_color_traded = _get_color(traded_varname, OPAQUE_ALPHA)
        time_traded, energy_traded, min_energy_traded, max_energy_traded = cls._prepare_input(
            device_dict, traded_varname, invert_y
        )

        time_series_traded = go.Bar(
            x=time_traded,
            y=energy_traded,
            marker=dict(
                color=fill_color_traded,
                line=dict(
                    color=color_traded,
                    width=1.0,
                ),
            ),
            name=traded_varname,
            showlegend=True,
            hoverinfo="y+name",
            xaxis="x",
            yaxis=yaxis,
        )

        if expected_varname is not None:
            color_expected = _get_color(expected_varname, OPAQUE_ALPHA)
            fill_color_expected = _get_color(expected_varname, TRANSPARENT_ALPHA)
            time_expected, energy_expected, min_energy_expected, max_energy_expected = (
                cls._prepare_input(device_dict, expected_varname)
            )
            time_series_expected = go.Bar(
                x=time_expected,
                y=energy_expected,
                marker=dict(
                    color=fill_color_expected,
                    line=dict(
                        color=color_expected,
                        width=1.0,
                    ),
                ),
                name=expected_varname,
                showlegend=True,
                hoverinfo="y+name",
                xaxis="x",
                yaxis=yaxis,
            )
            return [time_series_expected, time_series_traded] + cls._hoverinfo(
                time_expected, min_energy_expected, max_energy_expected, yaxis, only_time=True
            )
        return [time_series_traded] + cls._hoverinfo(
            time_traded, min_energy_traded, max_energy_traded, yaxis, only_time=True
        )

    @classmethod
    def _hoverinfo(cls, time, longterm_min, longterm_max, yaxis, only_time=False):
        # pylint: disable=too-many-arguments
        hoverinfo_max = go.Scatter(
            x=time,
            y=longterm_max,
            mode="none",
            name="longterm max",
            hoverinfo="y+name",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis,
        )
        hoverinfo_min = go.Scatter(
            x=time,
            y=longterm_min,
            mode="none",
            name="longterm min",
            hoverinfo="y+name",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis,
        )
        hoverinfo_time = go.Scatter(
            x=time,
            y=longterm_max,
            mode="none",
            hoverinfo="x",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis,
        )
        if only_time:
            return [hoverinfo_time]
        return [hoverinfo_max, hoverinfo_min, hoverinfo_time]

    @classmethod
    def _plot_candlestick_time_series_price(cls, device_dict, var_name, yaxis):
        # pylint: disable=too-many-locals
        time, trade_rate_list, longterm_min_trade_rate, longterm_max_trade_rate = (
            cls._prepare_input(device_dict, var_name)
        )
        plot_time = []
        plot_local_min_trade_rate = []
        plot_local_max_trade_rate = []
        plot_longterm_min_trade_rate = []
        plot_longterm_max_trade_rate = []
        for ii, _ in enumerate(trade_rate_list):
            if trade_rate_list[ii]:
                plot_time.append(time[ii])
                plot_local_min_trade_rate.append(limit_float_precision(min(trade_rate_list[ii])))
                plot_local_max_trade_rate.append(limit_float_precision(max(trade_rate_list[ii])))
                plot_longterm_min_trade_rate.append(
                    limit_float_precision(longterm_min_trade_rate[ii])
                )
                plot_longterm_max_trade_rate.append(
                    limit_float_precision(longterm_max_trade_rate[ii])
                )

        color = _get_color(var_name, OPAQUE_ALPHA)

        candle_stick = go.Candlestick(
            x=plot_time,
            open=plot_local_min_trade_rate,
            high=plot_longterm_max_trade_rate,
            low=plot_longterm_min_trade_rate,
            close=plot_local_max_trade_rate,
            yaxis=yaxis,
            xaxis="x",
            hoverinfo="none",
            name=var_name,
            increasing=dict(line=dict(color=color)),
            decreasing=dict(line=dict(color=color)),
        )
        hoverinfo_local_max = go.Scatter(
            x=plot_time,
            y=plot_local_max_trade_rate,
            mode="none",
            name="max",
            hoverinfo="y+name",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis,
        )
        hoverinfo_local_min = go.Scatter(
            x=plot_time,
            y=plot_local_min_trade_rate,
            mode="none",
            name="min",
            hoverinfo="y+name",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis,
        )

        return [candle_stick, hoverinfo_local_max, hoverinfo_local_min] + cls._hoverinfo(
            plot_time, plot_longterm_min_trade_rate, plot_longterm_max_trade_rate, yaxis
        )

    @classmethod
    def _prepare_input(cls, device_dict, var_name, invert_y=False):
        if var_name not in device_dict:
            return [], [], [], []
        x = list(device_dict[var_name].keys())
        y = list(device_dict[var_name].values())
        y_lower = list(device_dict["min_" + var_name].values())
        y_upper = list(device_dict["max_" + var_name].values())
        if invert_y:
            return x, _invert(y), _invert(y_lower), _invert(y_upper)
        return x, y, y_lower, y_upper

    @classmethod
    def _get_y2_range(cls, device_dict, var_name, start_at_zero=True):
        """
        Adds a 10% margin to the y2_range
        """
        data_max = max([abs(x) for x in list(device_dict[var_name].values()) if x is not None])
        data_max_margin = data_max + data_max * 0.1
        if start_at_zero:
            return [0, abs(data_max_margin)]
        return [-data_max_margin, data_max_margin]

    @classmethod
    def plot_device_profile(cls, device_dict, device_name, output_file, device_strategy):
        """
        Renders plot for asset traded energy, price and key KPI. Data defined by
        DeviceStatistics class of gsy-framework.
        """
        # pylint: disable=unidiomatic-typecheck,too-many-statements
        trade_energy_var_name = "trade_energy_kWh"
        sold_trade_energy_var_name = "sold_trade_energy_kWh"
        bought_trade_energy_var_name = "bought_trade_energy_kWh"
        data = []
        if isinstance(device_strategy, (StorageStrategy)):
            y1axis_key = "trade_price_eur"
            y2axis_key = trade_energy_var_name
            y3axis_key = "soc_history_%"
            yaxis_caption_list = [
                DEVICE_YAXIS[y1axis_key],
                DEVICE_YAXIS[y2axis_key],
                DEVICE_YAXIS[y3axis_key],
            ]

            data += cls._plot_candlestick_time_series_price(device_dict, y1axis_key, "y1")
            data += cls._plot_bar_time_series_traded(device_dict, y2axis_key, "y2")
            data += cls._plot_line_time_series(device_dict, y3axis_key)

            layout = cls._device_plot_layout(
                "overlay", f"{device_name}", "Time", yaxis_caption_list
            )

        elif isinstance(
            device_strategy, (LoadHoursStrategy, SCMLoadHoursStrategy, SCMLoadProfileStrategy)
        ):
            y1axis_key = "trade_price_eur"
            y2axis_key = trade_energy_var_name
            y3axis_key = "load_profile_kWh"
            yaxis_caption_list = [
                DEVICE_YAXIS[y1axis_key],
                DEVICE_YAXIS[y2axis_key],
                DEVICE_YAXIS[y3axis_key],
            ]

            data += cls._plot_candlestick_time_series_price(device_dict, y1axis_key, "y1")
            data += cls._plot_bar_time_series_traded(
                device_dict, y2axis_key, "y2", expected_varname=y3axis_key
            )
            data += cls._plot_line_time_series(device_dict, y3axis_key)

            layout = cls._device_plot_layout(
                "overlay", f"{device_name}", "Time", yaxis_caption_list
            )

        elif isinstance(device_strategy, (SmartMeterStrategy, SCMSmartMeterStrategy)):
            y1axis_key = "trade_price_eur"
            y2axis_key = trade_energy_var_name
            y3axis_key = "smart_meter_profile_kWh"
            yaxis_caption_list = [
                DEVICE_YAXIS[y1axis_key],
                DEVICE_YAXIS[y2axis_key],
                DEVICE_YAXIS[y3axis_key],
            ]

            data += cls._plot_candlestick_time_series_price(device_dict, y1axis_key, "y1")
            data += cls._plot_bar_time_series_traded(
                device_dict, y2axis_key, "y2", expected_varname=y3axis_key
            )
            data += cls._plot_line_time_series(device_dict, y3axis_key)
            layout = cls._device_plot_layout("overlay", device_name, "Time", yaxis_caption_list)

        elif isinstance(device_strategy, (PVStrategy, SCMPVUserProfile)):
            y1axis_key = "trade_price_eur"
            y2axis_key = trade_energy_var_name
            y3axis_key = "pv_production_kWh"
            yaxis_caption_list = [
                DEVICE_YAXIS[y1axis_key],
                DEVICE_YAXIS[y2axis_key],
                DEVICE_YAXIS[y3axis_key],
            ]

            data += cls._plot_candlestick_time_series_price(device_dict, y1axis_key, "y1")
            data += cls._plot_bar_time_series_traded(
                device_dict, y2axis_key, "y2", expected_varname=y3axis_key, invert_y=True
            )
            data += cls._plot_line_time_series(device_dict, y3axis_key)

            layout = cls._device_plot_layout(
                "overlay", f"{device_name}", "Time", yaxis_caption_list
            )

        elif isinstance(device_strategy, HeatPumpStrategy):
            y1axis_key = "trade_price_eur"
            y2axis_key = trade_energy_var_name
            y3axis_key = "storage_temp_C"
            yaxis_caption_list = [
                DEVICE_YAXIS[y1axis_key],
                DEVICE_YAXIS[y2axis_key],
                DEVICE_YAXIS[y3axis_key],
            ]

            data += cls._plot_candlestick_time_series_price(device_dict, y1axis_key, "y1")
            data += cls._plot_bar_time_series_traded(
                device_dict, y2axis_key, "y2", expected_varname=y2axis_key
            )
            data += cls._plot_line_time_series(device_dict, y3axis_key)

            layout = cls._device_plot_layout(
                "overlay", f"{device_name}", "Time", yaxis_caption_list
            )

        elif type(device_strategy) == FinitePowerPlant:
            y1axis_key = "trade_price_eur"
            y2axis_key = trade_energy_var_name
            y3axis_key = "production_kWh"
            yaxis_caption_list = [
                DEVICE_YAXIS[y1axis_key],
                DEVICE_YAXIS[y2axis_key],
                DEVICE_YAXIS[y3axis_key],
            ]

            data += cls._plot_candlestick_time_series_price(device_dict, y1axis_key, "y1")
            data += cls._plot_bar_time_series_traded(
                device_dict, y2axis_key, "y2", expected_varname=y3axis_key, invert_y=True
            )
            data += cls._plot_line_time_series(device_dict, y3axis_key)

            layout = cls._device_plot_layout(
                "overlay", f"{device_name}", "Time", yaxis_caption_list
            )
        elif type(device_strategy) in [CommercialStrategy, MarketMakerStrategy]:
            y1axis_key = "trade_price_eur"
            y2axis_key = sold_trade_energy_var_name
            yaxis_caption_list = [DEVICE_YAXIS[y1axis_key], DEVICE_YAXIS[y2axis_key]]

            data += cls._plot_candlestick_time_series_price(device_dict, y1axis_key, "y1")
            data += cls._plot_bar_time_series_traded(device_dict, y2axis_key, "y2", invert_y=True)

            layout = cls._device_plot_layout(
                "overlay", f"{device_name}", "Time", yaxis_caption_list
            )
        elif type(device_strategy) == InfiniteBusStrategy:
            y1axis_key = "trade_price_eur"
            y2axis_key = sold_trade_energy_var_name
            y3axis_key = bought_trade_energy_var_name

            yaxis_caption_list = [
                DEVICE_YAXIS[y1axis_key],
                DEVICE_YAXIS[y2axis_key],
                DEVICE_YAXIS[y3axis_key],
            ]

            data += cls._plot_candlestick_time_series_price(device_dict, y1axis_key, "y1")
            data += cls._plot_bar_time_series_traded(device_dict, y2axis_key, "y2")
            data += cls._plot_bar_time_series_traded(device_dict, y3axis_key, "y3")

            layout = cls._device_plot_layout(
                "overlay", f"{device_name}", "Time", yaxis_caption_list
            )

        else:
            return

        fig = go.Figure(data=data, layout=layout)
        py.offline.plot(fig, filename=output_file, auto_open=False)

    @staticmethod
    def _device_plot_layout(barmode, title, xaxis_caption, yaxis_caption_list):
        yaxes = {}
        d_domain_diff = 1 / len(yaxis_caption_list)
        for i, _ in enumerate(yaxis_caption_list):
            pointer = i / len(yaxis_caption_list)
            yaxes[f"yaxis{i+1}"] = dict(
                title=yaxis_caption_list[i],
                side="left" if i % 2 == 0 else "right",
                showgrid=True,
                domain=[pointer, pointer + d_domain_diff],
                rangemode="tozero",
                autorange=True,
            )

        return go.Layout(
            autosize=False,
            width=1250,
            height=1050,
            barmode=barmode,
            title=title,
            xaxis=dict(
                title=xaxis_caption,
                showgrid=True,
                anchor="y1",
                rangeslider=dict(visible=True, thickness=0.075, bgcolor="rgba(100,100,100,0.3)"),
            ),
            font=dict(size=16),
            showlegend=True,
            legend=dict(x=1.1, y=1),
            **yaxes,
        )
