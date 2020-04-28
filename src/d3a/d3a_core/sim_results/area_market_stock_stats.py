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


class StockStats:
    def __init__(self):
        self.state = {}

    def update(self, area):
        if area.name not in self.state:
            self.state[area.name] = {}

        last_past_market = area.last_past_market
        if last_past_market is None:
            return

        if last_past_market.time_slot not in self.state[area.name]:
            self.state[area.name][last_past_market.time_slot] = {}

        for trade in last_past_market.trades:
            tool_tip = f"Trade: {trade.seller_origin} --> {trade.buyer_origin} " \
                       f"({trade.offer.energy} kWh @ {trade.offer.energy_rate} € / kWh)"
            self.state[area.name][last_past_market.time_slot][trade.time] = \
                {"rate": trade.offer.energy_rate, "tool_tip": tool_tip}

        for id, bid in last_past_market.bids.items():
            tool_tip = f"{bid.buyer_origin} " \
                       f"Bid ({bid.energy} kWh @ {bid.energy_rate} € / kWh)"
            self.state[area.name][last_past_market.time_slot][bid.time] = \
                {"rate": bid.energy_rate, "tool_tip": tool_tip}

        for id, offer in last_past_market.offers.items():
            tool_tip = f"{offer.seller_origin} " \
                       f"Offer({offer.energy} kWh @ {offer.energy_rate} € / kWh)"
            self.state[area.name][last_past_market.time_slot][offer.time] = \
                {"rate": offer.energy_rate, "tool_tip": tool_tip}

        for child in area.children:
            if not child.children:
                continue
            self.update(child)
