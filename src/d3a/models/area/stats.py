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
from copy import copy
from pendulum import from_format
from statistics import mean, median

from d3a_interface.constants_limits import DATE_TIME_FORMAT
from d3a.constants import TIME_ZONE
from d3a import limit_float_precision
from d3a.d3a_core.util import area_name_from_area_or_iaa_name, add_or_create_key, \
    area_sells_to_child, child_buys_from_area
from d3a_interface.utils import convert_pendulum_to_str_in_dict, convert_str_to_pendulum_in_dict

default_trade_stats_dict = {
    "min_trade_rate": None,
    "max_trade_rate": None,
    "avg_trade_rate": None,
    "median_trade_rate": None,
    "total_traded_energy_kWh": None}


class AreaStats:
    def __init__(self, area_markets, area):
        self._markets = area_markets
        self._area = area
        self.aggregated_stats = {}
        self.market_bills = {}
        self.rate_stats_market = {}
        self.kpi = {}
        self.exported_energy = {}
        self.imported_energy = {}

    def get_state(self):
        return {
            "rate_stats_market": convert_pendulum_to_str_in_dict(self.rate_stats_market),
            "exported_energy": convert_pendulum_to_str_in_dict(self.exported_energy),
            "imported_energy": convert_pendulum_to_str_in_dict(self.imported_energy),
        }

    def load_state(self, saved_state):
        self.rate_stats_market = convert_str_to_pendulum_in_dict(saved_state["rate_stats_market"])
        self.exported_energy = convert_str_to_pendulum_in_dict(saved_state["exported_energy"])
        self.imported_energy = convert_str_to_pendulum_in_dict(saved_state["imported_energy"])

    def update_aggregated_stats(self, area_stats):
        self.aggregated_stats = area_stats

    def _extract_from_bills(self, trade_key):
        if self.current_market is None:
            return {}
        return {key: self.aggregated_stats["bills"][trade_key][key]
                for key in ["earned", "spent", "bought", "sold"]} \
            if "bills" in self.aggregated_stats \
               and trade_key in self.aggregated_stats["bills"] else {}

    def update_area_market_stats(self):
        if self.current_market is not None:
            self.market_bills[self.current_market.time_slot] = \
                {key: self._extract_from_bills(key)
                 for key in ["Accumulated Trades"]}
            self.rate_stats_market[self.current_market.time_slot] = \
                self.min_max_avg_median_rate_current_market()
            self._aggregate_exported_imported_energy()

    def get_last_market_stats_for_grid_tree(self):
        return {key.lower().replace(" ", "_"): self._extract_from_bills(key)
                for key in ["Accumulated Trades", "External Trades"]}

    def report_accounting(self, market, reporter, value, time):
        slot = market.time_slot
        if not self._markets.all_spot_markets:
            return
        market_timeslots = [m.time_slot for m in self._markets.all_spot_markets]
        if slot in market_timeslots:
            market.set_actual_energy(time, reporter, value)

    @property
    def cheapest_offers(self):
        cheapest_offers = []
        for market in self._markets.markets.values():
            cheapest_offers.extend(market.sorted_offers[0:1])
        return cheapest_offers

    def _get_market_bills(self, time_slot):
        return self.market_bills[time_slot] if time_slot in self.market_bills.keys() else None

    def _get_market_area_throughput(self, time_slot):
        return {"import": self.imported_energy[time_slot]
                if time_slot in self.imported_energy.keys() else None,
                "export": self.exported_energy[time_slot]
                if time_slot in self.exported_energy.keys() else None}

    def get_price_stats_current_market(self):
        if self.current_market is None:
            return None
        else:
            return self.rate_stats_market[self.current_market.time_slot] \
                if self.current_market.time_slot in self.rate_stats_market else None

    def min_max_avg_median_rate_current_market(self):
        out_dict = copy(default_trade_stats_dict)
        trade_volumes = [trade.offer.energy for trade in self.current_market.trades]
        trade_rates = [trade.offer.price/trade.offer.energy
                       for trade in self.current_market.trades]
        if len(trade_rates) > 0:
            out_dict["min_trade_rate"] = limit_float_precision(min(trade_rates))
            out_dict["max_trade_rate"] = limit_float_precision(max(trade_rates))
            out_dict["avg_trade_rate"] = limit_float_precision(mean(trade_rates))
            out_dict["median_trade_rate"] = limit_float_precision(median(trade_rates))
            out_dict["total_traded_energy_kWh"] = limit_float_precision(sum(trade_volumes))
        return out_dict

    @property
    def current_market(self):
        past_markets = list(self._markets.past_markets.values())
        return past_markets[-1] if len(past_markets) > 0 else None

    def get_market_stats(self, market_slot_list, dso=False):
        out_dict = {}
        for time_slot_str in market_slot_list:
            try:
                time_slot = from_format(time_slot_str, DATE_TIME_FORMAT, tz=TIME_ZONE)
            except ValueError:
                return {"ERROR": f"Time string '{time_slot_str}' is not following "
                                 f"the format '{DATE_TIME_FORMAT}'"}
            out_dict[time_slot_str] = copy(self.rate_stats_market.get(
                time_slot, default_trade_stats_dict))
            out_dict[time_slot_str]["market_bill"] = self._get_market_bills(time_slot)
            if dso:
                out_dict[time_slot_str]["area_throughput"] = \
                    self._get_market_area_throughput(time_slot)

        return out_dict

    def _aggregate_exported_imported_energy(self):
        if self._area.current_market is None:
            return None

        self.imported_energy = {}
        self.exported_energy = {}

        child_names = [area_name_from_area_or_iaa_name(c.name) for c in self._area.children]
        if getattr(self.current_market, 'trades', None) is not None:
            for trade in self.current_market.trades:
                if child_buys_from_area(trade, self._area.name, child_names):
                    add_or_create_key(self.exported_energy, self.current_market.time_slot,
                                      trade.offer.energy)
                if area_sells_to_child(trade, self._area.name, child_names):
                    add_or_create_key(self.imported_energy, self.current_market.time_slot,
                                      trade.offer.energy)
        if self.current_market.time_slot not in self.imported_energy:
            self.imported_energy[self.current_market.time_slot] = 0.
        if self.current_market.time_slot not in self.exported_energy:
            self.exported_energy[self.current_market.time_slot] = 0.
