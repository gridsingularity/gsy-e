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


class AreaStats:
    def __init__(self, area_markets):
        self._accumulated_past_price = 0
        self._accumulated_past_energy = 0
        self._markets = area_markets

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
