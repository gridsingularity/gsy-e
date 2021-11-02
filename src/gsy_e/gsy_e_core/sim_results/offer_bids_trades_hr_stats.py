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
from random import randint


class OfferBidTradeGraphStats:
    def __init__(self):
        self.state = {}
        self.color_mapping = {}

    def update(self, area):
        if area.name not in self.state:
            self.state[area.name] = {}

        last_past_market = area.last_past_market
        if last_past_market is None:
            return

        if last_past_market.time_slot not in self.state[area.name]:
            self.state[area.name][last_past_market.time_slot] = {}

        for bid in last_past_market.bid_history:
            self.check_and_create_color_mapping(bid.buyer_origin)
            self.check_and_create_list(area, last_past_market, bid)
            info_dict = {"rate": bid.energy_rate, "tag": "bid",
                         "color": self.color_mapping[bid.buyer_origin],
                         "buyer_origin": bid.buyer_origin, "energy": bid.energy}
            self.state[area.name][last_past_market.time_slot][bid.creation_time].append(info_dict)

        for offer in last_past_market.offer_history:
            self.check_and_create_color_mapping(offer.seller_origin)
            self.check_and_create_list(area, last_past_market, offer)
            self.state[area.name][last_past_market.time_slot][offer.creation_time].append(
                {"rate": offer.energy_rate, "tag": "offer",
                 "color": self.color_mapping[offer.seller_origin],
                 "seller_origin": offer.seller_origin, "energy": offer.energy})

        for trade in last_past_market.trades:
            self.check_and_create_color_mapping(trade.seller_origin)
            self.check_and_create_list(area, last_past_market, trade)
            info_dict = {"rate": trade.offer_bid.energy_rate, "tag": "trade",
                         "color": self.color_mapping[trade.seller_origin],
                         "seller_origin": trade.seller_origin, "buyer_origin": trade.buyer_origin,
                         "energy": trade.offer_bid.energy}
            self.state[area.name][last_past_market.time_slot][trade.creation_time].append(
                info_dict)

        for child in area.children:
            if not child.children:
                continue
            self.update(child)

    def check_and_create_color_mapping(self, origin):
        if origin not in self.color_mapping.keys():
            self.color_mapping[origin] = \
                f"rgb({randint(0, 255)}, {randint(0, 255)}, {randint(0, 255)})"

    def check_and_create_list(self, area, last_past_market, trade):
        if trade.creation_time not in self.state[area.name][last_past_market.time_slot].keys():
            self.state[area.name][last_past_market.time_slot][trade.creation_time] = []
