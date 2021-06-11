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
import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict  # noqa
from copy import deepcopy
import json
from pendulum import DateTime, parse
from d3a.events import MarketEvent
from d3a_interface.utils import datetime_to_string_incl_seconds, key_in_dict_and_not_none


@dataclass
class Clearing:
    rate: float
    energy: float


def my_converter(o):
    if isinstance(o, DateTime):
        return o.isoformat()


@dataclass
class Offer:
    id: str
    time: datetime
    price: float
    energy: float
    seller: str
    original_offer_price: float = None
    seller_origin: str = None
    seller_origin_id: str = None
    seller_id: str = None
    energy_rate: float = field(init=False)

    def __post_init__(self):
        self.id = str(self.id)
        self.energy_rate = self.price / self.energy

    def update_price(self, price):
        self.price = price
        self.energy_rate = self.price / self.energy

    def __repr__(self):
        return ("<Offer('{s.id!s:.6s}', '{s.energy} kWh@{s.price}', '{s.seller} {rate}'>"
                .format(s=self, rate=self.energy_rate))

    def __str__(self):
        return ("{{{s.id!s:.6s}}} [origin: {s.seller_origin}] "
                "[{s.seller}]: {s.energy} kWh @ {s.price} @ {rate}"
                .format(s=self, rate=self.energy_rate))

    def to_json_string(self, **kwargs):
        """Convert the Offer object into its JSON representation.

        Args:
            **kwargs: additional key-value pairs to be added to the JSON representation.
        """
        offer_dict = deepcopy(asdict(self))
        if kwargs:
            offer_dict = {**offer_dict, **kwargs}

        offer_dict["type"] = "Offer"
        offer_dict.pop('energy_rate', None)

        return json.dumps(offer_dict, default=my_converter)

    def serializable_dict(self):
        return {
            "type": "Offer",
            "id": self.id,
            "energy": self.energy,
            "energy_rate": self.energy_rate,
            "original_offer_price": self.original_offer_price,
            "seller": self.seller,
            "seller_origin": self.seller_origin,
            "seller_origin_id": self.seller_origin_id,
            "seller_id": self.seller_id,
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
                 offer.original_offer_price, offer.seller_origin, offer.seller_origin_id,
                 offer.seller_id)


@dataclass
class Bid:
    id: str
    time: datetime
    price: float
    energy: float
    buyer: str
    original_bid_price: float = None
    buyer_origin: str = None
    energy_rate: float = None
    buyer_origin_id: str = None
    buyer_id: str = None

    def __post_init__(self):
        self.id = str(self.id)
        if self.energy_rate is None:
            self.energy_rate = self.price / self.energy

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
        return "rate [ct./kWh]", "energy [kWh]", "price [ct.]", "buyer"

    def _to_csv(self):
        rate = round(self.energy_rate, 4)
        return rate, self.energy, self.price, self.buyer

    def to_json_string(self, **kwargs):
        """Convert the Bid object to its JSON representation. Additional elements can be added.

        Args:
            **kwargs: additional key-value pairs to be added to the JSON representation.
        """
        bid_dict = deepcopy(asdict(self))
        if kwargs:
            bid_dict = {**bid_dict, **kwargs}

        bid_dict["type"] = "Bid"

        return json.dumps(bid_dict, default=my_converter)

    def serializable_dict(self):
        return {
            "type": "Bid",
            "id": self.id,
            "energy": self.energy,
            "energy_rate": self.energy_rate,
            "original_bid_price": self.original_bid_price,
            "buyer_origin": self.buyer_origin,
            "buyer_origin_id": self.buyer_origin_id,
            "buyer_id": self.buyer_id,
            "buyer": self.buyer,
            "time": datetime_to_string_incl_seconds(self.time)
        }


def offer_or_bid_from_json_string(offer_or_bid, current_time=None):
    offer_bid_dict = json.loads(offer_or_bid)
    object_type = offer_bid_dict.pop("type")
    if "price" not in offer_bid_dict:
        offer_bid_dict["price"] = offer_bid_dict["energy_rate"] * offer_bid_dict["energy"]
    if object_type == "Offer":
        offer_bid_dict.pop('energy_rate', None)
        offer_bid_dict['time'] = current_time
        return Offer(**offer_bid_dict)
    elif object_type == "Bid":
        return Bid(**offer_bid_dict)


@dataclass
class TradeBidOfferInfo:
    original_bid_rate: float
    propagated_bid_rate: float
    original_offer_rate: float
    propagated_offer_rate: float
    trade_rate: float

    def to_json_string(self):
        return json.dumps(asdict(self), default=my_converter)

    @classmethod
    def len(cls):
        return cls.len()


def trade_bid_info_from_json_string(info_string):
    info_dict = json.loads(info_string)
    return TradeBidOfferInfo(**info_dict)


@dataclass
class Trade:
    id: str
    time: datetime
    offer: Offer
    seller: str
    buyer: str
    residual: Offer or Bid = None
    already_tracked: bool = False
    offer_bid_trade_info: TradeBidOfferInfo = None
    seller_origin: float = None
    buyer_origin: str = None
    fee_price: float = None
    seller_origin_id: str = None
    buyer_origin_id: str = None
    seller_id: str = None
    buyer_id: str = None

    def __str__(self):
        return (
            "{{{s.id!s:.6s}}} [origin: {s.seller_origin} -> {s.buyer_origin}] "
            "[{s.seller} -> {s.buyer}] {s.offer.energy} kWh @ {s.offer.price} {rate} "
            "{s.offer.id} [fee: {s.fee_price} cts.]".
            format(s=self, rate=round(self.offer.energy_rate, 8))
        )

    @classmethod
    def _csv_fields(cls):
        return (tuple(cls.__dataclass_fields__.keys())[1:2] + ("rate [ct./kWh]", "energy [kWh]") +
                tuple(cls.__dataclass_fields__.keys())[3:5])

    def _to_csv(self):
        rate = round(self.offer.energy_rate, 4)
        return (tuple(asdict(self).values())[1:2] +
                (rate, self.offer.energy) +
                tuple(asdict(self).values())[3:5])

    def to_json_string(self):
        # __dict__ instead of asdict to not recursively deserialize objects
        trade_dict = deepcopy(self.__dict__)
        trade_dict["offer"] = trade_dict["offer"].to_json_string()
        if key_in_dict_and_not_none(trade_dict, "residual"):
            trade_dict["residual"] = trade_dict["residual"].to_json_string()
        if key_in_dict_and_not_none(trade_dict, "offer_bid_trade_info"):
            trade_dict["offer_bid_trade_info"] = (
                trade_dict["offer_bid_trade_info"].to_json_string())
        return json.dumps(trade_dict, default=my_converter)

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
            "seller_origin_id": self.seller_origin_id,
            "buyer_origin_id": self.buyer_origin_id,
            "seller_id": self.seller_id,
            "buyer_id": self.buyer_id,
            "seller": self.seller,
            "fee_price": self.fee_price,
            "time": datetime_to_string_incl_seconds(self.time)
        }


def trade_from_json_string(trade_string, current_time):
    trade_dict = json.loads(trade_string)
    trade_dict["offer"] = offer_or_bid_from_json_string(trade_dict["offer"], current_time)
    if key_in_dict_and_not_none(trade_dict, "residual"):
        trade_dict["residual"] = offer_or_bid_from_json_string(trade_dict["residual"],
                                                               current_time)
    trade_dict["time"] = parse(trade_dict["time"])
    if key_in_dict_and_not_none(trade_dict, "offer_bid_trade_info"):
        trade_dict["offer_bid_trade_info"] = (
            trade_bid_info_from_json_string(trade_dict["offer_bid_trade_info"]))
    return Trade(**trade_dict)


class BalancingOffer(Offer):

    def __repr__(self):
        return "<BalancingOffer('{s.id!s:.6s}', '{s.energy} kWh@{s.price}', '{s.seller} {rate}'>"\
            .format(s=self, rate=self.energy_rate)

    def __str__(self):
        return "<BalancingOffer{{{s.id!s:.6s}}} [{s.seller}]: " \
               "{s.energy} kWh @ {s.price} @ {rate}>".format(s=self,
                                                             rate=self.energy_rate)


@dataclass
class BalancingTrade:
    id: str
    time: datetime
    offer: Offer
    seller: str
    buyer: str
    residual: Offer or Bid = None
    offer_bid_trade_info: str = None
    seller_origin: float = None
    buyer_origin: str = None
    fee_price: float = None
    seller_origin_id: str = None
    buyer_origin_id: str = None
    seller_id: str = None
    buyer_id: str = None

    def __post_init__(self):
        self.id = str(self.id)

    def __str__(self):
        return (
            "{{{s.id!s:.6s}}} [{s.seller} -> {s.buyer}] "
            "{s.offer.energy} kWh @ {s.offer.price} {rate} {s.offer.id}".
            format(s=self, rate=self.offer.energy_rate)
        )

    @classmethod
    def _csv_fields(cls):
        return (tuple(cls.__dataclass_fields__.keys())[1:2] + ("rate [ct./kWh]", "energy [kWh]") +
                tuple(cls.__dataclass_fields__.keys())[3:5])

    def _to_csv(self):
        rate = round(self.offer.energy_rate, 4)
        return (tuple(asdict(self).values())[1:2] +
                (rate, self.offer.energy) +
                tuple(asdict(self).values())[3:5])


@dataclass
class MarketClearingState:
    cumulative_offers: dict = field(default_factory=dict)
    cumulative_bids: dict = field(default_factory=dict)
    clearing: dict = field(default_factory=dict)

    @classmethod
    def _csv_fields(cls):
        return "time", "rate [ct./kWh]"


@dataclass
class BidOfferMatch:
    bid: Bid
    selected_energy: float
    offer: Offer
    trade_rate: float


def parse_event_and_parameters_from_json_string(payload):
    data = json.loads(payload["data"])
    kwargs = data["kwargs"]
    for key in ["offer", "existing_offer", "new_offer"]:
        if key in kwargs:
            kwargs[key] = offer_or_bid_from_json_string(kwargs[key])
    if "trade" in kwargs:
        kwargs["trade"] = trade_from_json_string(kwargs["trade"])
    for key in ["bid", "existing_bid", "new_bid"]:
        if key in kwargs:
            kwargs[key] = offer_or_bid_from_json_string(kwargs[key])
    if "bid_trade" in kwargs:
        kwargs["bid_trade"] = trade_from_json_string(kwargs["bid_trade"])
    event_type = MarketEvent(data["event_type"])
    return event_type, kwargs
