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
from typing import Dict  # noqa
from copy import deepcopy
import json
from pendulum import DateTime, parse
from d3a.events import MarketEvent
from d3a_interface.utils import datetime_to_string_incl_seconds, key_in_dict_and_not_none

Clearing = namedtuple('Clearing', ('rate', 'energy'))


def my_converter(o):
    if isinstance(o, DateTime):
        return o.isoformat()


class Offer:
    def __init__(self, id, time, price, energy, seller,
                 original_offer_price=None, seller_origin=None):
        self.id = str(id)
        self.real_id = id
        self.price = price
        self.original_offer_price = original_offer_price
        self.energy = energy
        self.seller = seller
        self.seller_origin = seller_origin
        self.energy_rate = price / energy
        self.time = time

    def update_price(self, price):
        self.price = price
        self.energy_rate = self.price / self.energy

    def __repr__(self):
        return "<Offer('{s.id!s:.6s}', '{s.energy} kWh@{s.price}', '{s.seller} {rate}'>"\
            .format(s=self, rate=self.energy_rate)

    def __str__(self):
        return "{{{s.id!s:.6s}}} [origin: {s.seller_origin}] " \
               "[{s.seller}]: {s.energy} kWh @ {s.price} @ {rate}"\
            .format(s=self, rate=self.energy_rate)

    def to_JSON_string(self):
        offer_dict = deepcopy(self.__dict__)
        offer_dict["type"] = "Offer"
        offer_dict.pop('energy_rate', None)
        return json.dumps(offer_dict, default=my_converter)

    def serializable_dict(self):
        return {
            "type": "Offer",
            "id": self.id,
            "energy": self.energy,
            "energy_rate": self.energy_rate,
            "seller": self.seller,
            "seller_origin": self.seller_origin,
            "time": datetime_to_string_incl_seconds(self.time)
        }

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
        return 'rate [ct./kWh]', 'energy [kWh]', 'price [ct.]', 'seller'

    def _to_csv(self):
        rate = round(self.energy_rate, 4)
        return rate, self.energy, self.price, self.seller


def copy_offer(offer):
    return Offer(offer.id, offer.time, offer.price, offer.energy, offer.seller,
                 offer.original_offer_price, offer.seller_origin)


def offer_from_JSON_string(offer_string, current_time):
    offer_dict = json.loads(offer_string)
    object_type = offer_dict.pop("type")
    assert object_type == "Offer"
    real_id = offer_dict.pop('real_id')
    offer_dict.pop('energy_rate', None)
    offer_dict['time'] = current_time
    offer = Offer(**offer_dict)
    offer.real_id = real_id
    return offer


class Bid(namedtuple('Bid', ('id', 'time', 'price', 'energy', 'buyer',
                             'original_bid_price', 'buyer_origin', 'energy_rate'))):
    def __new__(cls, id, time, price, energy, buyer, original_bid_price=None,
                buyer_origin=None, energy_rate=None):
        if energy_rate is None:
            energy_rate = price / energy
        # overridden to give the residual field a default value
        return super(Bid, cls).__new__(cls, str(id), time, price, energy, buyer,
                                       original_bid_price, buyer_origin, energy_rate)

    def __repr__(self):
        return (
            "<Bid {{{s.id!s:.6s}}} [{s.buyer}] "
            "{s.energy} kWh @ {s.price} {rate}>".format(s=self, rate=self.energy_rate)
        )

    def __str__(self):
        return (
            "{{{s.id!s:.6s}}} [origin: {s.buyer_origin}] [{s.buyer}] "
            "{s.energy} kWh @ {s.price} {rate}".format(s=self, rate=self.energy_rate)
        )

    @classmethod
    def _csv_fields(cls):
        return 'rate [ct./kWh]', 'energy [kWh]', 'price [ct.]', 'buyer'

    def _to_csv(self):
        rate = round(self.energy_rate, 4)
        return rate, self.energy, self.price, self.buyer

    def to_JSON_string(self):
        bid_dict = self._asdict()
        bid_dict["type"] = "Bid"
        return json.dumps(bid_dict, default=my_converter)

    def serializable_dict(self):
        return {
            "type": "Bid",
            "id": self.id,
            "energy": self.energy,
            "energy_rate": self.energy_rate,
            "buyer_origin": self.buyer_origin,
            "buyer": self.buyer,
            "time": datetime_to_string_incl_seconds(self.time)
        }


def bid_from_JSON_string(bid_string):
    bid_dict = json.loads(bid_string)
    object_type = bid_dict.pop("type")
    assert object_type == "Bid"
    return Bid(**bid_dict)


def offer_or_bid_from_JSON_string(offer_or_bid, current_time):
    offer_bid_dict = json.loads(offer_or_bid)
    object_type = offer_bid_dict.pop("type")
    offer_bid_dict['time'] = current_time
    if object_type == "Offer":
        real_id = offer_bid_dict.pop('real_id')
        offer = Offer(**offer_bid_dict)
        offer.real_id = real_id
        return offer
    elif object_type == "Bid":
        return Bid(**offer_bid_dict)


class TradeBidOfferInfo(namedtuple('TradeBidOfferInfo', ('original_bid_rate',
                                                         'propagated_bid_rate',
                                                         'original_offer_rate',
                                                         'propagated_offer_rate',
                                                         'trade_rate'))):
    def to_JSON_string(self):
        return json.dumps(self._asdict(), default=my_converter)

    @classmethod
    def len(cls):
        return len(cls._fields)


def trade_bid_info_from_JSON_string(info_string):
    info_dict = json.loads(info_string)
    return TradeBidOfferInfo(**info_dict)


class Trade(namedtuple('Trade', ('id', 'time', 'offer', 'seller', 'buyer', 'residual',
                                 'already_tracked', 'offer_bid_trade_info', 'seller_origin',
                                 'buyer_origin', 'fee_price'))):
    def __new__(cls, id, time, offer, seller, buyer, residual=None,
                already_tracked=False, offer_bid_trade_info=None,
                seller_origin=None, buyer_origin=None, fee_price=None):
        # overridden to give the residual field a default value
        return super(Trade, cls).__new__(cls, id, time, offer, seller, buyer, residual,
                                         already_tracked, offer_bid_trade_info, seller_origin,
                                         buyer_origin, fee_price)

    def __str__(self):
        return (
            "{{{s.id!s:.6s}}} [origin: {s.seller_origin} -> {s.buyer_origin}] "
            "[{s.seller} -> {s.buyer}] {s.offer.energy} kWh @ {s.offer.price} {rate} "
            "{s.offer.id} [fee: {s.fee_price} cts.]".
            format(s=self, rate=round(self.offer.energy_rate, 8))
        )

    @classmethod
    def _csv_fields(cls):
        return (cls._fields[1:2] + ('rate [ct./kWh]', 'energy [kWh]') +
                cls._fields[3:5])

    def _to_csv(self):
        rate = round(self.offer.energy_rate, 4)
        return self[1:2] + (rate, self.offer.energy) + self[3:5]

    def to_JSON_string(self):
        trade_dict = self._asdict()
        trade_dict['offer'] = trade_dict['offer'].to_JSON_string()
        trade_dict['residual'] = trade_dict['residual'].to_JSON_string() \
            if trade_dict['residual'] is not None else None
        trade_dict['time'] = trade_dict['time'].isoformat()
        return json.dumps(trade_dict)

    def serializable_dict(self):
        return {
            "type": "Trade",
            "match_type": "Offer" if isinstance(self.offer, Offer) else "Bid",
            "id": self.id,
            "offer_bid_id": self.offer.id,
            "residual_id": self.residual.id if self.residual is not None else None,
            "energy": self.offer.energy,
            "energy_rate": self.offer.energy_rate,
            "price": self.offer.energy * self.offer.energy_rate,
            "buyer": self.buyer,
            "buyer_origin": self.buyer_origin,
            "seller_origin": self.seller_origin,
            "seller": self.seller,
            "fee_price": self.fee_price,
            "time": datetime_to_string_incl_seconds(self.time)
        }


def trade_from_JSON_string(trade_string, current_time):
    trade_dict = json.loads(trade_string)
    trade_dict['offer'] = offer_or_bid_from_JSON_string(trade_dict['offer'], current_time)
    if 'residual' in trade_dict and trade_dict['residual'] is not None:
        trade_dict['residual'] = offer_or_bid_from_JSON_string(trade_dict['residual'],
                                                               current_time)
    trade_dict['time'] = parse(trade_dict['time'])
    if key_in_dict_and_not_none(trade_dict, 'offer_bid_trade_info'):
        keys = ['original_bid_rate',
                'propagated_bid_rate',
                'original_offer_rate',
                'propagated_offer_rate',
                'trade_rate']
        values = trade_dict['offer_bid_trade_info']
        trade_dict['offer_bid_trade_info'] = dict(zip(keys, values))
        trade_dict['offer_bid_trade_info'] = TradeBidOfferInfo(
            **trade_dict['offer_bid_trade_info'])
    return Trade(**trade_dict)


class BalancingOffer(Offer):

    def __repr__(self):
        return "<BalancingOffer('{s.id!s:.6s}', '{s.energy} kWh@{s.price}', '{s.seller} {rate}'>"\
            .format(s=self, rate=self.energy_rate)

    def __str__(self):
        return "<BalancingOffer{{{s.id!s:.6s}}} [{s.seller}]: " \
               "{s.energy} kWh @ {s.price} @ {rate}>".format(s=self,
                                                             rate=self.energy_rate)


class BalancingTrade(namedtuple('BalancingTrade', ('id', 'time', 'offer', 'seller',
                                                   'buyer', 'residual', 'offer_bid_trade_info',
                                                   'seller_origin', 'buyer_origin', 'fee_price'))):
    def __new__(cls, id, time, offer, seller, buyer, residual=None, offer_bid_trade_info=None,
                seller_origin=None, buyer_origin=None, fee_price=None):
        # overridden to give the residual field a default value
        return super(BalancingTrade, cls).__new__(cls, id, time, offer, seller,
                                                  buyer, residual, offer_bid_trade_info,
                                                  seller_origin, buyer_origin, fee_price)

    def __str__(self):
        return (
            "{{{s.id!s:.6s}}} [{s.seller} -> {s.buyer}] "
            "{s.offer.energy} kWh @ {s.offer.price} {rate} {s.offer.id}".
            format(s=self, rate=self.offer.energy_rate)
        )

    @classmethod
    def _csv_fields(cls):
        return (cls._fields[1:2] + ('rate [ct./kWh]', 'energy [kWh]') +
                cls._fields[3:5])

    def _to_csv(self):
        rate = round(self.offer.energy_rate, 4)
        return self[1:2] + (rate, self.offer.energy) + self[3:5]


class MarketClearingState:
    def __init__(self):
        self.cumulative_offers = dict()  # type: Dict[DateTime, dict()]
        self.cumulative_bids = dict()  # type: Dict[DateTime, dict()]
        self.clearing = {}  # type: Dict[DateTime, tuple()]

    @classmethod
    def _csv_fields(cls):
        return 'time', 'rate [ct./kWh]'


BidOfferMatch = namedtuple('BidOfferMatch', ['bid', 'bid_energy', 'offer', 'offer_energy'])


def parse_event_and_parameters_from_json_string(payload):
    data = json.loads(payload["data"])
    kwargs = data["kwargs"]
    for key in ["offer", "existing_offer", "new_offer"]:
        if key in kwargs:
            kwargs[key] = offer_from_JSON_string(kwargs[key])
    if "trade" in kwargs:
        kwargs["trade"] = trade_from_JSON_string(kwargs["trade"])
    for key in ["bid", "existing_bid", "new_bid"]:
        if key in kwargs:
            kwargs[key] = bid_from_JSON_string(kwargs[key])
    if "bid_trade" in kwargs:
        kwargs["bid_trade"] = trade_from_JSON_string(kwargs["bid_trade"])
    event_type = MarketEvent(data["event_type"])
    return event_type, kwargs
