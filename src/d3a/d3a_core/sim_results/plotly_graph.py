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
import plotly as py
import plotly.graph_objs as go
import pendulum
import os

from d3a.constants import TIME_ZONE
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a import limit_float_precision

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
purple = 'rgba(156, 110, 177, alpha)'
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

OPAQUE_ALPHA = 1
TRANSPARENT_ALPHA = 0.4


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
    def common_layout(barmode: str, title: str, ytitle: str, xtitle: str, xrange: list,
                      showlegend=True, hovermode="x"):
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
            showlegend=showlegend,
            hovermode=hovermode
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
                day_set.add(
                    pendulum.datetime(ti.year, ti.month, ti.day, ti.hour, ti.minute, tz=TIME_ZONE)
                )

        day_list = sorted(list(day_set))
        if len(day_list) == 0:
            raise ValueError("There is no time information in plot {}".format(title))

        start_time = pendulum.datetime(
            day_list[0].year, day_list[0].month, day_list[0].day,
            day_list[0].hour, day_list[0].minute, day_list[0].second, tz=TIME_ZONE
        )
        end_time = pendulum.datetime(
            day_list[-1].year, day_list[-1].month, day_list[-1].day,
            day_list[-1].hour, day_list[-1].minute, day_list[-1].second, tz=TIME_ZONE)

        return [start_time, end_time], data

    @classmethod
    def plot_slider_graph(cls, fig, stats_plot_dir, area_name, market_slot_data_mapping):
        steps = []
        for i in range(len(market_slot_data_mapping)):
            step = dict(
                method="update",
                args=[{"visible": [False] * len(fig.data)},
                      {"title": "Slider switched to slot: " + str(i)}],  # layout attribute
            )
            for k in range(market_slot_data_mapping[i].start,
                           market_slot_data_mapping[i].end):
                step["args"][0]["visible"][k] = True  # Toggle i'th trace to "visible"
            if market_slot_data_mapping[i].start == market_slot_data_mapping[i].end and \
                    0 < market_slot_data_mapping[i].end < len(fig.data):
                step["args"][0]["visible"][market_slot_data_mapping[i].start] = True
            steps.append(step)
        sliders = [dict(
            active=0,
            currentvalue={"prefix": "MarketSlot: "},
            pad={"t": len(market_slot_data_mapping)},
            steps=steps
        )]
        output_file = os.path.join(stats_plot_dir, f"offer_bid_trade_history.html")
        barmode = "group"
        title = f"OFFER BID TRADE AREA: {area_name}"
        xtitle = 'Time'
        ytitle = 'Rate [€ cents / kWh]'

        fig.update_layout(autosize=True, barmode=barmode, width=1200, height=700, title=title,
                          yaxis=dict(title=ytitle), xaxis=dict(title=xtitle),
                          font=dict(size=16), showlegend=False, sliders=sliders)

        py.offline.plot(fig, filename=output_file, auto_open=False)

    @classmethod
    def plot_bar_graph(cls, barmode: str, title: str, xtitle: str, ytitle: str, data, iname: str,
                       time_range=None, showlegend=True, hovermode="x"):
        if time_range is None:
            try:
                time_range, data = cls.modify_time_axis(data, title)
            except ValueError:
                return

        layout = cls.common_layout(
            barmode, title, ytitle, xtitle, time_range, showlegend, hovermode=hovermode
        )
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
    def _plot_line_time_series(cls, device_dict, var_name):
        color = _get_color(var_name, OPAQUE_ALPHA)
        fill_color = _get_color(var_name, TRANSPARENT_ALPHA)
        time, var_data, longterm_min_var_data, longterm_max_var_data = \
            cls.prepare_input(device_dict, var_name)
        yaxis = "y"
        connectgaps = True
        line = dict(color=color,
                    width=0.8)
        time_series = go.Scatter(
            x=time,
            y=var_data,
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
            x=time,
            y=longterm_max_var_data,
            fill=None,
            fillcolor=fill_color,
            line=dict(color='rgba(255,255,255,0)'),
            name=f"longterm max",
            showlegend=False,
            hoverinfo='y+name',
            xaxis="x",
            yaxis=yaxis,
            connectgaps=connectgaps
        )
        longterm_min_hover = go.Scatter(
            x=time,
            y=longterm_min_var_data,
            fill=None,
            fillcolor=fill_color,
            line=dict(color='rgba(255,255,255,0)'),
            name=f"longterm min",
            showlegend=False,
            hoverinfo='y+name',
            xaxis="x",
            yaxis=yaxis,
            connectgaps=connectgaps
        )
        shade = go.Scatter(
            x=time,
            y=longterm_max_var_data,
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
        hoverinfo_time = go.Scatter(
            x=time,
            y=longterm_max_var_data,
            mode="none",
            hoverinfo="x",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis
        )

        # it is not possible to use cls._hoverinfo here because the order matters here:
        return [longterm_min_hover, shade, time_series, longterm_max_hover, hoverinfo_time]

    @classmethod
    def _plot_bar_time_series_storage(cls, device_dict, var_name):
        color = _get_color(var_name, OPAQUE_ALPHA)
        fill_color = _get_color(var_name, TRANSPARENT_ALPHA)
        time, traded_energy, longterm_min_traded_energy, longterm_max_traded_energy = \
            cls.prepare_input(device_dict, var_name)
        yaxis = "y2"
        time_series = go.Bar(
            x=time,
            y=traded_energy,
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

        return [time_series] + \
            cls._hoverinfo(time, longterm_min_traded_energy, longterm_max_traded_energy, yaxis)

    @classmethod
    def _plot_bar_time_series_traded_expected(cls, device_dict, expected_varname, traded_varname,
                                              invert_y=False):
        color_expected = _get_color(expected_varname, OPAQUE_ALPHA)
        fill_color_expected = _get_color(expected_varname, TRANSPARENT_ALPHA)
        color_traded = _get_color(traded_varname, OPAQUE_ALPHA)
        fill_color_traded = _get_color(traded_varname, OPAQUE_ALPHA)
        time_expected, energy_expected, min_energy_expected, max_energy_expected = \
            cls.prepare_input(device_dict, expected_varname)
        time_traded, energy_traded, min_energy_traded, max_energy_traded = \
            cls.prepare_input(device_dict, traded_varname, invert_y)

        yaxis = "y2"
        time_series_expected = go.Bar(
            x=time_expected,
            y=energy_expected,
            marker=dict(
                color=fill_color_expected,
                line=dict(
                    color=color_expected,
                    width=1.,
                )
            ),
            name=expected_varname,
            showlegend=True,
            hoverinfo='y+name',
            xaxis="x",
            yaxis=yaxis,
        )
        time_series_traded = go.Bar(
            x=time_traded,
            y=energy_traded,
            marker=dict(
                color=fill_color_traded,
                line=dict(
                    color=color_traded,
                    width=1.,
                )
            ),
            name=traded_varname,
            showlegend=True,
            hoverinfo='y+name',
            xaxis="x",
            yaxis=yaxis,
        )

        return [time_series_expected, time_series_traded] + \
            cls._hoverinfo(time_expected, min_energy_expected, max_energy_expected, yaxis,
                           only_time=True)

    @classmethod
    def _hoverinfo(cls, time, longterm_min, longterm_max, yaxis, only_time=False):
        hoverinfo_max = go.Scatter(
            x=time,
            y=longterm_max,
            mode="none",
            name="longterm max",
            hoverinfo="y+name",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis
        )
        hoverinfo_min = go.Scatter(
            x=time,
            y=longterm_min,
            mode="none",
            name="longterm min",
            hoverinfo="y+name",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis
        )
        hoverinfo_time = go.Scatter(
            x=time,
            y=longterm_max,
            mode="none",
            hoverinfo="x",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis
        )
        if only_time:
            return [hoverinfo_time]
        else:
            return [hoverinfo_max, hoverinfo_min, hoverinfo_time]

    @classmethod
    def _plot_candlestick_time_series_price(cls, device_dict, var_name):

        time, trade_rate_list, longterm_min_trade_rate, longterm_max_trade_rate = \
            cls.prepare_input(device_dict, var_name)
        plot_time = []
        plot_local_min_trade_rate = []
        plot_local_max_trade_rate = []
        plot_longterm_min_trade_rate = []
        plot_longterm_max_trade_rate = []
        for ii in range(len(trade_rate_list)):
            if trade_rate_list[ii] is not None:
                plot_time.append(time[ii])
                plot_local_min_trade_rate.append(limit_float_precision(min(trade_rate_list[ii])))
                plot_local_max_trade_rate.append(limit_float_precision(max(trade_rate_list[ii])))
                plot_longterm_min_trade_rate.append(
                    limit_float_precision(longterm_min_trade_rate[ii]))
                plot_longterm_max_trade_rate.append(
                    limit_float_precision(longterm_max_trade_rate[ii]))

        yaxis = "y3"
        color = _get_color(var_name, OPAQUE_ALPHA)

        candle_stick = go.Candlestick(x=plot_time,
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
            yaxis=yaxis
        )
        hoverinfo_loacl_min = go.Scatter(
            x=plot_time,
            y=plot_local_min_trade_rate,
            mode="none",
            name="min",
            hoverinfo="y+name",
            xaxis="x",
            showlegend=False,
            yaxis=yaxis
        )

        return [candle_stick, hoverinfo_local_max, hoverinfo_loacl_min] + \
            cls._hoverinfo(plot_time, plot_longterm_min_trade_rate,
                           plot_longterm_max_trade_rate, yaxis)

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
    def _get_y2_range(cls, device_dict, var_name, start_at_zero=True):
        """
        Adds a 10% margin to the y2_range
        """
        data_max = max([abs(x) for x in list(device_dict[var_name].values()) if x is not None])
        data_max_margin = data_max + data_max * 0.1
        if start_at_zero:
            return [0, abs(data_max_margin)]
        else:
            return [-data_max_margin, data_max_margin]

    @classmethod
    def plot_device_profile(cls, device_dict, device_name, output_file, device_strategy):
        trade_energy_var_name = "trade_energy_kWh"
        data = []
        # Trade price graph (y3):
        data += cls._plot_candlestick_time_series_price(device_dict, "trade_price_eur")
        # Traded energy graph (y2):
        if isinstance(device_strategy, StorageStrategy):
            y1axis_key = "soc_history_%"
            data += cls._plot_bar_time_series_storage(device_dict, trade_energy_var_name)
            y2axis_range = cls._get_y2_range(device_dict, trade_energy_var_name,
                                             start_at_zero=False)
            y2axis_caption = "Bought/Sold [kWh]"
        elif isinstance(device_strategy, LoadHoursStrategy):
            y1axis_key = "load_profile_kWh"
            data += cls._plot_bar_time_series_traded_expected(device_dict, y1axis_key,
                                                              trade_energy_var_name)
            y2axis_caption = "Demand/Traded [kWh]"
            y2axis_range = cls._get_y2_range(device_dict, "load_profile_kWh")
        elif isinstance(device_strategy, PVStrategy):
            y1axis_key = "pv_production_kWh"
            data += cls._plot_bar_time_series_traded_expected(device_dict, y1axis_key,
                                                              trade_energy_var_name, invert_y=True)
            y2axis_range = cls._get_y2_range(device_dict, y1axis_key)
            y2axis_caption = "Supply/Traded [kWh]"
        else:
            return
        # SOC, load_curve, pv production graph (y1):
        data += cls._plot_line_time_series(device_dict, y1axis_key)
        y1axis_caption = DEVICE_YAXIS[y1axis_key]

        layout = cls._device_plot_layout("overlay", f"{device_name}", 'Time',
                                         y1axis_caption, y2axis_caption, y2axis_range)
        fig = go.Figure(data=data, layout=layout)
        py.offline.plot(fig, filename=output_file, auto_open=False)

    @staticmethod
    def _device_plot_layout(barmode, title, xaxis_caption, yaxis_caption, y2axis_caption,
                            y2axis_range):
        return go.Layout(
            autosize=False,
            width=1200,
            height=700,
            barmode=barmode,
            title=title,
            xaxis=dict(
                title=xaxis_caption,
                showgrid=True,
                anchor="y3",
                rangeslider=dict(visible=True,
                                 thickness=0.075,
                                 bgcolor='rgba(100,100,100,0.3)'
                                 )
            ),
            yaxis=dict(
                title=yaxis_caption,
                side='left',
                showgrid=True,
                domain=[0.66, 1],
                rangemode='tozero',
                autorange=True
            ),
            yaxis2=dict(
                title=y2axis_caption,
                side='right',
                range=y2axis_range,
                showgrid=True,
                domain=[0.33, 0.66],
                autorange=False
            ),
            yaxis3=dict(
                title='Energy rate [€/kWh]',
                domain=[0.0, 0.33],
                side='left',
                showgrid=True,
                autorange=True
            ),
            font=dict(
                size=12
            ),
            showlegend=True,
            legend=dict(x=1.1, y=1)
        )
