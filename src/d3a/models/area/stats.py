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
from statistics import mean
from d3a_interface.constants_limits import DATE_TIME_FORMAT
from d3a.constants import TIME_ZONE, DEFAULT_PRECISION


class AreaStats:
    def __init__(self, area_markets):
        self._accumulated_past_price = 0
        self._accumulated_past_energy = 0
        self._markets = area_markets
        self.aggregated_stats = {}

    def update_aggregated_stats(self, area_stats):
        self.aggregated_stats = area_stats

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

    def min_max_avg_rate_market(self, time_slot):
        out_dict = {"min_trade_rate": None,
                    "max_trade_rate": None,
                    "avg_trade_rate": None}
        for market in self._markets.all_spot_markets:
            if market.time_slot == time_slot and len(market.trades) > 0:
                trade_rates = [trade.offer.price/trade.offer.energy for trade in market.trades]
                out_dict["min_trade_rate"] = round(min(trade_rates), DEFAULT_PRECISION)
                out_dict["max_trade_rate"] = round(max(trade_rates), DEFAULT_PRECISION)
                out_dict["avg_trade_rate"] = round(mean(trade_rates), DEFAULT_PRECISION)
        return out_dict

    def get_market_price_stats(self, market_slot_list):
        out_dict = {}
        for time_slot_str in market_slot_list:
            try:
                time_slot = from_format(time_slot_str, DATE_TIME_FORMAT, tz=TIME_ZONE)
            except ValueError:
                return {"ERROR": f"Time string '{time_slot_str}' is not following "
                                 f"the format '{DATE_TIME_FORMAT}'"}
            out_dict[time_slot_str] = self.min_max_avg_rate_market(time_slot)
        return out_dict
