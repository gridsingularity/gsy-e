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
from pendulum import from_format
from statistics import mean, median
from d3a_interface.constants_limits import DATE_TIME_FORMAT
from d3a.constants import TIME_ZONE
from d3a import limit_float_precision
from d3a.d3a_core.util import area_name_from_area_or_iaa_name, add_or_create_key, \
    area_sells_to_child, child_buys_from_area


class AreaStats:
    def __init__(self, area_markets):
        self._accumulated_past_price = 0
        self._accumulated_past_energy = 0
        self._markets = area_markets
        self.aggregated_stats = {}
        self.market_bills = {}
        self.rate_stats_market = {}
        self.exported_energy = {}
        self.imported_energy = {}

    def aggregate_exported_imported_energy(self, area):
        if self.current_market is None:
            return
        child_names = [area_name_from_area_or_iaa_name(c.name) for c in area.children]
        for trade in self.current_market.trades:
            if child_buys_from_area(trade, area.name, child_names):
                add_or_create_key(self.exported_energy, self.current_market.time_slot_str,
                                  trade.offer.energy)
            if area_sells_to_child(trade, area.name, child_names):
                add_or_create_key(self.imported_energy, self.current_market.time_slot_str,
                                  trade.offer.energy)
        if self.current_market.time_slot_str not in self.imported_energy:
            self.imported_energy[self.current_market.time_slot_str] = 0.
        if self.current_market.time_slot_str not in self.exported_energy:
            self.exported_energy[self.current_market.time_slot_str] = 0.

    def update_aggregated_stats(self, area_stats):
        self.aggregated_stats = area_stats

    def update_area_market_stats(self):
        if self.current_market is not None:
            self.market_bills[self.current_market.time_slot] = \
                {key: self.aggregated_stats["bills"]['Accumulated Trades'][key]
                 for key in ["earned", "spent", "bought", "sold"]} \
                if "bills" in self.aggregated_stats else None
            self.rate_stats_market[self.current_market.time_slot] = \
                self.min_max_avg_median_rate_current_market()

    def update_accumulated(self):
        self._accumulated_past_price = sum(
            market.accumulated_trade_price
            for market in self._markets.past_markets.values()
        )
        self._accumulated_past_energy = sum(
            market.accumulated_trade_energy
            for market in self._markets.past_markets.values()
        )

    @property
    def _offer_count(self):
        return sum(
            len(m.offers)
            for m in self._markets.all_spot_markets
        )

    @property
    def _trade_count(self):
        return sum(
            len(m.trades)
            for m in self._markets.all_spot_markets
        )

    @property
    def historical_avg_rate(self):
        price = sum(
            market.accumulated_trade_price
            for market in self._markets.markets.values()
        ) + self._accumulated_past_price
        energy = sum(
            market.accumulated_trade_energy
            for market in self._markets.markets.values()
        ) + self._accumulated_past_energy
        return price / energy if energy else 0

    @property
    def historical_min_max_price(self):
        min_max_prices = [
            (m.min_trade_price, m.max_trade_price)
            for m in self._markets.all_spot_markets
        ]
        return (
            min(p[0] for p in min_max_prices),
            max(p[1] for p in min_max_prices)
        )

    def report_accounting(self, market, reporter, value, time):
        slot = market.time_slot
        if not self._markets.all_spot_markets:
            return
        market_timeslots = [m.time_slot for m in self._markets.all_spot_markets]
        if slot in market_timeslots:
            market.set_actual_energy(time, reporter, value)
        else:
            raise RuntimeError("Reporting energy for unknown market")

    @property
    def cheapest_offers(self):
        cheapest_offers = []
        for market in self._markets.markets.values():
            cheapest_offers.extend(market.sorted_offers[0:1])
        return cheapest_offers

    def _get_market_bills(self, time_slot):
        return self.market_bills[time_slot] if time_slot in self.market_bills.keys() else None

    def get_price_stats_current_market(self):
        if self.current_market is None:
            return None
        else:
            return self.rate_stats_market[self.current_market.time_slot] \
                if self.current_market.time_slot in self.rate_stats_market else None

    def min_max_avg_median_rate_current_market(self):
        out_dict = {"min_trade_rate": None,
                    "max_trade_rate": None,
                    "avg_trade_rate": None,
                    "median_trade_rate": None,
                    "total_traded_energy_kWh": None}
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

    def get_market_stats(self, market_slot_list):
        if self.current_market is None:
            return {"INFO": "No market stats available yet"}
        out_dict = {}
        for time_slot_str in market_slot_list:
            try:
                time_slot = from_format(time_slot_str, DATE_TIME_FORMAT, tz=TIME_ZONE)
            except ValueError:
                return {"ERROR": f"Time string '{time_slot_str}' is not following "
                                 f"the format '{DATE_TIME_FORMAT}'"}
            if time_slot > self.current_market.time_slot:
                out_dict[time_slot_str] = {"ERROR": "This market is not in the past."}
            else:
                if time_slot in self.rate_stats_market:
                    out_dict[time_slot_str] = self.rate_stats_market[time_slot]
                    out_dict[time_slot_str]["market_bill"] = self._get_market_bills(time_slot)
        return out_dict
