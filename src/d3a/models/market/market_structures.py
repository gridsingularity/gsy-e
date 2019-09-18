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
from collections import namedtuple
from typing import Dict # noqa


class Offer:
    def __init__(self, id, price, energy, seller, original_offer_price=None, energy_origin=None):
        self.id = str(id)
        self.real_id = id
        self.price = price
        self.original_offer_price = original_offer_price
        self.energy = energy
        self.seller = seller
        self.energy_origin = energy_origin

    def __repr__(self):
        return "<Offer('{s.id!s:.6s}', '{s.energy} kWh@{s.price}', '{s.seller} {rate}'>"\
            .format(s=self, rate=self.price / self.energy)

    def __str__(self):
        return "{{{s.id!s:.6s}}} [ORIGIN: {s.energy_origin}] " \
               "[{s.seller}]: {s.energy} kWh @ {s.price} @ {rate}"\
            .format(s=self, rate=self.price / self.energy)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id and \
            self.price == other.price and \
            self.original_offer_price == other.original_offer_price and \
            self.energy == other.energy and \
            self.seller == other.seller

    @classmethod
    def _csv_fields(cls):
        return 'id', 'rate [ct./kWh]', 'energy [kWh]', 'price [ct.]', 'seller'

    def _to_csv(self):
        rate = round(self.price / self.energy, 4)
        return self.id, rate, self.energy, self.price, self.seller


class Bid(namedtuple('Bid', ('id', 'price', 'energy', 'buyer', 'seller',
                             'original_bid_price', 'energy_origin'))):
    def __new__(cls, id, price, energy, buyer, seller, original_bid_price=None,
                energy_origin=None):
        # overridden to give the residual field a default value
        return super(Bid, cls).__new__(cls, str(id), price, energy, buyer, seller,
                                       original_bid_price, energy_origin)

    def __repr__(self):
        return (
            "<Bid {{{s.id!s:.6s}}} [{s.buyer}] [{s.seller}] "
            "{s.energy} kWh @ {s.price} {rate}>".format(s=self, rate=self.price / self.energy)
        )

    def __str__(self):
        return (
            "{{{s.id!s:.6s}}} [ORIGIN: {s.energy_origin}] [{s.buyer}] [{s.seller}] "
            "{s.energy} kWh @ {s.price} {rate}".format(s=self, rate=self.price / self.energy)
        )

    @classmethod
    def _csv_fields(cls):
        return 'id', 'rate [ct./kWh]', 'energy [kWh]', 'price [ct.]', 'buyer'

    def _to_csv(self):
        rate = round(self.price / self.energy, 4)
        return self.id, rate, self.energy, self.price, self.buyer


class Trade(namedtuple('Trade', ('id', 'time', 'offer', 'seller',
                                 'buyer', 'residual', 'already_tracked',
                                 'original_trade_rate', 'energy_origin'))):
    def __new__(cls, id, time, offer, seller, buyer, residual=None,
                already_tracked=False, original_trade_rate=None, energy_origin=None):
        # overridden to give the residual field a default value
        return super(Trade, cls).__new__(cls, id, time, offer, seller, buyer, residual,
                                         already_tracked, original_trade_rate, energy_origin)

    def __str__(self):
        mark_partial = "(partial)" if self.residual is not None else ""
        return (
            "{{{s.id!s:.6s}}} [ORIGIN: {s.energy_origin}] [{s.seller} -> {s.buyer}] "
            "{s.offer.energy} kWh {p} @ {s.offer.price} {rate} {s.offer.id}".
            format(s=self, p=mark_partial, rate=round(self.offer.price / self.offer.energy, 8))
        )

    @classmethod
    def _csv_fields(cls):
        return (cls._fields[:2] + ('rate [ct./kWh]', 'energy [kWh]') +
                cls._fields[3:5])

    def _to_csv(self):
        rate = round(self.offer.price / self.offer.energy, 4)
        return self[:2] + (rate, self.offer.energy) + self[3:5]


class BalancingOffer(Offer):

    def __repr__(self):
        return "<BalancingOffer('{s.id!s:.6s}', '{s.energy} kWh@{s.price}', '{s.seller} {rate}'>"\
            .format(s=self, rate=self.price / self.energy)

    def __str__(self):
        return "<BalancingOffer{{{s.id!s:.6s}}} [{s.seller}]: " \
               "{s.energy} kWh @ {s.price} @ {rate}>".format(s=self,
                                                             rate=self.price / self.energy)


class BalancingTrade(namedtuple('BalancingTrade', ('id', 'time', 'offer', 'seller',
                                                   'buyer', 'residual', 'original_trade_rate'))):
    def __new__(cls, id, time, offer, seller, buyer, residual=None, original_trade_rate=None):
        # overridden to give the residual field a default value
        return super(BalancingTrade, cls).__new__(cls, id, time, offer, seller,
                                                  buyer, residual, original_trade_rate)

    def __str__(self):
        mark_partial = "(partial)" if self.residual is not None else ""
        return (
            "{{{s.id!s:.6s}}} [{s.seller} -> {s.buyer}] "
            "{s.offer.energy} kWh {p} @ {s.offer.price} {rate} {s.offer.id}".
            format(s=self, p=mark_partial, rate=self.offer.price / self.offer.energy)
        )

    @classmethod
    def _csv_fields(cls):
        return (cls._fields[:2] + ('rate [ct./kWh]', 'energy [kWh]') +
                cls._fields[3:5])

    def _to_csv(self):
        rate = round(self.offer.price / self.offer.energy, 4)
        return self[:2] + (rate, self.offer.energy) + self[3:5]


class MarketClearingState:
    def __init__(self):
        self.cumulative_offers = dict()  # type Dict[Datetime, dict()]
        self.cumulative_bids = dict()  # type Dict[Datetime, dict()]
        self.clearing = {}  # type: Dict[Datetime, tuple()]

    @classmethod
    def _csv_fields(cls):
        return 'time', 'rate [ct./kWh]'
