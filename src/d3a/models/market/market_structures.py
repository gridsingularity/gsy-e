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
import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Union  # noqa

from d3a_interface.utils import datetime_to_string_incl_seconds, key_in_dict_and_not_none
from pendulum import DateTime, parse

from d3a.events import MarketEvent


@dataclass
class Clearing:
    rate: float
    energy: float


def my_converter(o):
    if isinstance(o, DateTime):
        return o.isoformat()
    return None


class BaseBidOffer:
    """Base class defining shared functionality of Bid and Offer market structures."""
    def __init__(self, id: str, time: datetime, price: float, energy: float,
                 attributes: Dict = None, requirements: List[Dict] = None):
        self.id = str(id)
        self.time = time
        self.price = price
        self.energy = energy
        self.energy_rate = self.price / self.energy
        self.attributes = attributes
        self.requirements = requirements

    def update_price(self, price: float) -> None:
        self.price = price
        self.energy_rate = self.price / self.energy

    def update_energy(self, energy: float) -> None:
        self.energy = energy
        self.energy_rate = self.price / self.energy

    def to_json_string(self, **kwargs) -> str:
        """Convert the Offer or Bid object into its JSON representation.

        Args:
            **kwargs: additional key-value pairs to be added to the JSON representation.
        """
        obj_dict = deepcopy(self.__dict__)
        if kwargs:
            obj_dict = {**obj_dict, **kwargs}

        obj_dict["type"] = self.__class__.__name__

        return json.dumps(obj_dict, default=my_converter)

    def to_csv(self) -> Tuple:
        rate = round(self.energy_rate, 4)
        return (rate, self.energy, self.price,
                self.seller if isinstance(self, Offer) else self.buyer)

    def serializable_dict(self) -> Dict:
        return {
            "type": self.__class__.__name__,
            "id": self.id,
            "energy": self.energy,
            "energy_rate": self.energy_rate,
            "time": datetime_to_string_incl_seconds(self.time),
            "attributes": self.attributes,
            "requirements": self.requirements
        }


class Offer(BaseBidOffer):
    def __init__(self, id: str, time: datetime, price: float,
                 energy: float, seller: str, original_offer_price: float = None,
                 seller_origin: str = None, seller_origin_id: str = None,
                 seller_id: str = None,
                 attributes: Dict = None,
                 requirements: List[Dict] = None):
        super().__init__(id=id, time=time, price=price, energy=energy,
                         attributes=attributes, requirements=requirements)
        self.seller = seller
        self.original_offer_price = original_offer_price or price
        self.seller_origin = seller_origin
        self.seller_origin_id = seller_origin_id
        self.seller_id = seller_id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return ("<Offer('{s.id!s:.6s}', '{s.energy} kWh@{s.price}', '{s.seller} {rate}'>"
                .format(s=self, rate=self.energy_rate))

    def __str__(self) -> str:
        return ("{{{s.id!s:.6s}}} [origin: {s.seller_origin}] "
                "[{s.seller}]: {s.energy} kWh @ {s.price} @ {rate}"
                .format(s=self, rate=self.energy_rate))

    def serializable_dict(self) -> Dict:
        return {**super().serializable_dict(),
                "original_offer_price": self.original_offer_price,
                "seller": self.seller,
                "seller_origin": self.seller_origin,
                "seller_origin_id": self.seller_origin_id,
                "seller_id": self.seller_id,
                }

    def __eq__(self, other) -> bool:
        return (self.id == other.id and
                self.price == other.price and
                self.original_offer_price == other.original_offer_price and
                self.energy == other.energy and
                self.seller == other.seller and
                self.seller_origin_id == other.seller_origin_id and
                self.attributes == other.attributes and
                self.requirements == other.requirements)

    @classmethod
    def csv_fields(cls):
        return "rate [ct./kWh]", "energy [kWh]", "price [ct.]", "seller"


def copy_offer(offer) -> Offer:
    return Offer(offer.id, offer.time, offer.price, offer.energy, offer.seller,
                 offer.original_offer_price, offer.seller_origin, offer.seller_origin_id,
                 offer.seller_id, attributes=offer.attributes, requirements=offer.requirements)


class Bid(BaseBidOffer):
    def __init__(self, id: str, time: datetime, price: float,
                 energy: float, buyer: str,
                 original_bid_price: float = None,
                 buyer_origin: str = None,
                 buyer_origin_id: str = None,
                 buyer_id: str = None,
                 attributes: Dict = None,
                 requirements: List[Dict] = None
                 ):
        super().__init__(id=id, time=time, price=price, energy=energy,
                         attributes=attributes, requirements=requirements)
        self.buyer = buyer
        self.original_bid_price = original_bid_price or price
        self.buyer_origin = buyer_origin
        self.buyer_origin_id = buyer_origin_id
        self.buyer_id = buyer_id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return (
            "<Bid {{{s.id!s:.6s}}} [{s.buyer}] "
            "{s.energy} kWh @ {s.price} {rate}>".format(s=self, rate=self.energy_rate)
        )

    def __str__(self) -> str:
        return (
            "{{{s.id!s:.6s}}} [origin: {s.buyer_origin}] [{s.buyer}] "
            "{s.energy} kWh @ {s.price} {rate}".format(s=self, rate=self.energy_rate)
        )

    def serializable_dict(self) -> Dict:
        return {**super().serializable_dict(),
                "original_bid_price": self.original_bid_price,
                "buyer_origin": self.buyer_origin,
                "buyer_origin_id": self.buyer_origin_id,
                "buyer_id": self.buyer_id,
                "buyer": self.buyer,
                }

    @classmethod
    def csv_fields(cls):
        return "rate [ct./kWh]", "energy [kWh]", "price [ct.]", "buyer"

    def __eq__(self, other) -> bool:
        return (self.id == other.id and
                self.price == other.price and
                self.original_bid_price == other.original_bid_price and
                self.energy == other.energy and
                self.buyer == other.buyer and
                self.buyer_origin_id == other.buyer_origin_id and
                self.attributes == other.attributes and
                self.requirements == other.requirements)


def offer_or_bid_from_json_string(offer_or_bid, current_time=None) -> Union[Offer, Bid]:
    offer_bid_dict = json.loads(offer_or_bid)
    object_type = offer_bid_dict.pop("type")

    offer_bid_dict.pop("energy_rate", None)

    if object_type == "Offer":
        offer_bid_dict["time"] = current_time
        return Offer(**offer_bid_dict)
    if object_type == "Bid":
        return Bid(**offer_bid_dict)


@dataclass
class TradeBidOfferInfo:
    original_bid_rate: float
    propagated_bid_rate: float
    original_offer_rate: float
    propagated_offer_rate: float
    trade_rate: float

    def to_json_string(self) -> str:
        return json.dumps(asdict(self), default=my_converter)

    @classmethod
    def len(cls) -> int:
        return cls.len()


def trade_bid_info_from_json_string(info_string) -> TradeBidOfferInfo:
    info_dict = json.loads(info_string)
    return TradeBidOfferInfo(**info_dict)


@dataclass
class Trade:
    id: str
    time: datetime
    offer_bid: Union[Offer, Bid]
    seller: str
    buyer: str
    residual: Union[Offer, Bid] = None
    already_tracked: bool = False
    offer_bid_trade_info: TradeBidOfferInfo = None
    seller_origin: str = None
    buyer_origin: str = None
    fee_price: float = None
    seller_origin_id: str = None
    buyer_origin_id: str = None
    seller_id: str = None
    buyer_id: str = None

    def __str__(self) -> str:
        return (
            "{{{s.id!s:.6s}}} [origin: {s.seller_origin} -> {s.buyer_origin}] "
            "[{s.seller} -> {s.buyer}] {s.offer_bid.energy} kWh @ {s.offer_bid.price} {rate} "
            "{s.offer_bid.id} [fee: {s.fee_price} cts.]".
            format(s=self, rate=round(self.offer_bid.energy_rate, 8))
        )

    @classmethod
    def csv_fields(cls) -> Tuple:
        return (tuple(cls.__dataclass_fields__.keys())[1:2] + ("rate [ct./kWh]", "energy [kWh]") +
                tuple(cls.__dataclass_fields__.keys())[3:5])

    def to_csv(self) -> Tuple:
        rate = round(self.offer_bid.energy_rate, 4)
        return (tuple(asdict(self).values())[1:2] +
                (rate, self.offer_bid.energy) +
                tuple(asdict(self).values())[3:5])

    def to_json_string(self) -> str:
        # __dict__ instead of asdict to not recursively deserialize objects
        trade_dict = deepcopy(self.__dict__)
        trade_dict["offer_bid"] = trade_dict["offer_bid"].to_json_string()
        if key_in_dict_and_not_none(trade_dict, "residual"):
            trade_dict["residual"] = trade_dict["residual"].to_json_string()
        if key_in_dict_and_not_none(trade_dict, "offer_bid_trade_info"):
            trade_dict["offer_bid_trade_info"] = (
                trade_dict["offer_bid_trade_info"].to_json_string())
        return json.dumps(trade_dict, default=my_converter)

    @property
    def is_bid_trade(self) -> bool:
        """Check if the instance is a bid trade."""
        return isinstance(self.offer_bid, Bid)

    @property
    def is_offer_trade(self) -> bool:
        """Check if the instance is an offer trade."""
        return isinstance(self.offer_bid, Offer)

    def serializable_dict(self) -> Dict:
        return {
            "type": "Trade",
            "match_type": type(self.offer_bid).__name__,
            "id": self.id,
            "offer_bid_id": self.offer_bid.id,
            "residual_id": self.residual.id if self.residual is not None else None,
            "energy": self.offer_bid.energy,
            "energy_rate": self.offer_bid.energy_rate,
            "price": self.offer_bid.price,
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


def trade_from_json_string(trade_string, current_time=None) -> Trade:
    trade_dict = json.loads(trade_string)
    trade_dict["offer_bid"] = offer_or_bid_from_json_string(trade_dict["offer_bid"], current_time)
    if key_in_dict_and_not_none(trade_dict, "residual"):
        trade_dict["residual"] = offer_or_bid_from_json_string(trade_dict["residual"],
                                                               current_time)
    trade_dict["time"] = parse(trade_dict["time"])
    if key_in_dict_and_not_none(trade_dict, "offer_bid_trade_info"):
        trade_dict["offer_bid_trade_info"] = (
            trade_bid_info_from_json_string(trade_dict["offer_bid_trade_info"]))
    return Trade(**trade_dict)


class BalancingOffer(Offer):

    def __repr__(self) -> str:
        return ("<BalancingOffer('{s.id!s:.6s}', '{s.energy} kWh@{s.price}', "
                "'{s.seller} {rate}'>".format(s=self, rate=self.energy_rate))

    def __str__(self) -> str:
        return ("<BalancingOffer{{{s.id!s:.6s}}} [{s.seller}]: "
                "{s.energy} kWh @ {s.price} @ {rate}>".format(s=self, rate=self.energy_rate))


@dataclass
class BalancingTrade:
    id: str
    time: datetime
    offer_bid: Union[Offer, Bid]
    seller: str
    buyer: str
    residual: Union[Offer, Bid] = None
    offer_bid_trade_info: TradeBidOfferInfo = None
    seller_origin: float = None
    buyer_origin: str = None
    fee_price: float = None
    seller_origin_id: str = None
    buyer_origin_id: str = None
    seller_id: str = None
    buyer_id: str = None

    def __post_init__(self):
        self.id = str(self.id)

    def __str__(self) -> str:
        return (
            "{{{s.id!s:.6s}}} [{s.seller} -> {s.buyer}] "
            "{s.offer_bid.energy} kWh @ {s.offer_bid.price} {rate} {s.offer_bid.id}".
            format(s=self, rate=self.offer_bid.energy_rate)
        )

    @classmethod
    def csv_fields(cls) -> Tuple:
        return (tuple(cls.__dataclass_fields__.keys())[1:2] + ("rate [ct./kWh]", "energy [kWh]") +
                tuple(cls.__dataclass_fields__.keys())[3:5])

    def to_csv(self) -> Tuple:
        rate = round(self.offer_bid.energy_rate, 4)
        return (tuple(asdict(self).values())[1:2] +
                (rate, self.offer_bid.energy) +
                tuple(asdict(self).values())[3:5])


@dataclass
class MarketClearingState:
    cumulative_offers: dict = field(default_factory=dict)
    cumulative_bids: dict = field(default_factory=dict)
    clearing: dict = field(default_factory=dict)

    @classmethod
    def csv_fields(cls) -> Tuple:
        return "time", "rate [ct./kWh]"


def parse_event_and_parameters_from_json_string(payload) -> Tuple:
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


class AvailableMarketTypes(Enum):
    SPOT = 0
    BALANCING = 1
    SETTLEMENT = 2


PAST_MARKET_TYPE_FILE_SUFFIX_MAPPING = {
    AvailableMarketTypes.SPOT: "",
    AvailableMarketTypes.BALANCING: "-balancing",
    AvailableMarketTypes.SETTLEMENT: "-settlement",
}
