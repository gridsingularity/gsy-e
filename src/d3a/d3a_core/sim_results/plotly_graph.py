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
import plotly as py
import plotly.graph_objs as go
import pendulum
from sortedcontainers import SortedDict

from d3a.constants import TIME_ZONE
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
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
