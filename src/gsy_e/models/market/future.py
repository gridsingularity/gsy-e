"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
# pylint: disable=too-many-arguments, too-many-locals, no-member
from collections import UserDict
from copy import deepcopy
from logging import getLogger
from typing import Dict, List, Optional, TYPE_CHECKING

from gsy_framework.constants_limits import ConstSettings, GlobalConfig, DATE_TIME_FORMAT
from gsy_framework.data_classes import Bid, Offer
from gsy_framework.utils import is_time_slot_in_simulation_duration
from pendulum import DateTime, duration

from gsy_e.gsy_e_core.blockchain_interface import NonBlockchainInterface
from gsy_e.models.market import GridFee
from gsy_e.models.market import lock_market_action
from gsy_e.models.market.two_sided import TwoSidedMarket

if TYPE_CHECKING:
    from gsy_e.models.area.event_dispatcher import AreaDispatcher
    from gsy_e.models.config import SimulationConfig

log = getLogger(__name__)


class FutureMarketException(Exception):
    """Exception specific to the Future markets."""


class FutureOrders(UserDict):
    """Special mapping object to keep track of a future market's orders."""
    def __init__(self, *args, **kwargs):
        self.slot_order_mapping = {}
        super().__init__(*args, **kwargs)

    def __setitem__(self, order_id, order):
        self.data[order_id] = order
        if order.time_slot not in self.slot_order_mapping:
            self.slot_order_mapping[order.time_slot] = []
        self.slot_order_mapping[order.time_slot].append(order)

    def __delitem__(self, order_id):
        order = self.data.get(order_id, None)
        if order:
            self.slot_order_mapping[order.time_slot].remove(order)
        del self.data[order_id]


class FutureMarkets(TwoSidedMarket):
    """Class responsible for future markets."""

    def __init__(self, bc: Optional[NonBlockchainInterface] = None,
                 notification_listener: Optional["AreaDispatcher"] = None,
                 readonly: bool = False,
                 grid_fee_type: int = ConstSettings.MASettings.GRID_FEE_TYPE,
                 grid_fees: Optional[GridFee] = None,
                 name: Optional[str] = None) -> None:
        super().__init__(time_slot=None, bc=bc, notification_listener=notification_listener,
                         readonly=readonly, grid_fee_type=grid_fee_type,
                         grid_fees=grid_fees, name=name, in_sim_duration=True)

        self._offers = FutureOrders()
        self._bids = FutureOrders()

    @property
    def offers(self) -> FutureOrders:
        """Return the {offer_id: offer} mapping."""
        return self._offers

    @offers.setter
    def offers(self, orders) -> None:
        """Wrap the setter of _orders in order to build a FutureOrders object."""
        self._offers = FutureOrders(orders)

    @property
    def bids(self) -> FutureOrders:
        """Return the {bid_id: bid} mapping."""
        return self._bids

    @bids.setter
    def bids(self, orders) -> None:
        """Wrap the setter of _orders in order to build a FutureOrders object."""
        self._bids = FutureOrders(orders)

    @property
    def slot_bid_mapping(self):
        """Return the {time_slot: [bids_list]} mapping."""
        return self.bids.slot_order_mapping

    @property
    def slot_offer_mapping(self) -> Dict:
        """Return the {time_slot: [offers_list]} mapping."""
        return self.offers.slot_order_mapping

    @property
    def slot_trade_mapping(self) -> Dict:
        """Return the {time_slot: [trades_list]} mapping."""
        mapping = {time_slot: [] for time_slot in self.slot_bid_mapping.keys()}
        for trade in self.trades:
            mapping[trade.time_slot].append(trade)
        return mapping

    def __repr__(self):  # pragma: no cover
        return (f"<{self._class_name} bids:{self.slot_bid_mapping}"
                f"offer: {self.slot_offer_mapping} trades: {self.slot_trade_mapping}>")

    @property
    def _debug_log_market_type_identifier(self) -> str:
        return "[FUTURE]"

    @property
    def market_time_slots(self) -> List[DateTime]:
        """Return list of all time slots of future markets."""
        return list(self.slot_bid_mapping.keys())

    @property
    def market_time_slots_str(self) -> List[str]:
        """Return all the time slots of future markets represented as strings."""
        return [time_slot.format(DATE_TIME_FORMAT) for time_slot in self.market_time_slots]

    @property
    def info(self) -> Dict:
        """Return information about the market instance."""
        return {
            "name": self.name,
            "id": self.id,
            "duration_min": GlobalConfig.slot_length.minutes,
            "time_slots": self.market_time_slots_str,
            "type_name": self.type_name}

    def orders_per_slot(self) -> Dict[str, Dict]:
        """Return all orders in the market per time slot."""
        orders_dict = {}
        for time_slot, bids_list in self.slot_bid_mapping.items():
            time_slot = time_slot.format(DATE_TIME_FORMAT)
            if time_slot not in orders_dict:
                orders_dict[time_slot] = {"bids": [], "offers": []}
            orders_dict[time_slot]["bids"].extend([bid.serializable_dict() for bid in bids_list])

        for time_slot, offers_list in self.slot_offer_mapping.items():
            time_slot = time_slot.format(DATE_TIME_FORMAT)
            if time_slot not in orders_dict:
                orders_dict[time_slot] = {"bids": [], "offers": []}
            orders_dict[time_slot]["offers"].extend(
                [offer.serializable_dict() for offer in offers_list])
        return orders_dict

    @staticmethod
    def _remove_old_orders_from_list(order_list: List, current_market_time_slot: DateTime) -> List:
        return [
            order for order in order_list if order.time_slot > current_market_time_slot
        ]

    def _expire_orders(self, orders: "FutureOrders", current_market_time_slot: DateTime) -> None:
        """Remove old orders (time_slot in the past)."""
        for order_id, order in deepcopy(list(orders.items())):
            if order.time_slot <= current_market_time_slot:
                if isinstance(order, Offer):
                    self.delete_offer(order_id)
                else:
                    self.delete_bid(order_id)
        for time_slot in deepcopy(list(orders.slot_order_mapping.keys())):
            if time_slot <= current_market_time_slot:
                del orders.slot_order_mapping[time_slot]

    def delete_orders_in_old_future_markets(self, last_slot_to_be_deleted: DateTime
                                            ) -> None:
        """Delete order and trade buffers."""
        self._expire_orders(self.offers, last_slot_to_be_deleted)
        self._expire_orders(self.bids, last_slot_to_be_deleted)

        self.offer_history = self._remove_old_orders_from_list(
            self.offer_history, last_slot_to_be_deleted)
        self.bid_history = self._remove_old_orders_from_list(
            self.bid_history, last_slot_to_be_deleted)
        self.trades = self._remove_old_orders_from_list(
            self.trades, last_slot_to_be_deleted)

    @staticmethod
    def _get_market_slot_duration(_current_time: DateTime, config: "SimulationConfig") -> duration:
        return config.slot_length

    def _create_future_markets(
            self, start_time: DateTime, end_time: DateTime, config: "SimulationConfig") -> None:
        future_time_slot = start_time
        while future_time_slot <= end_time:
            if (future_time_slot not in self.slot_bid_mapping and
                    is_time_slot_in_simulation_duration(future_time_slot, config)):
                self.bids.slot_order_mapping[future_time_slot] = []
                self.offers.slot_order_mapping[future_time_slot] = []
            future_time_slot = future_time_slot.add(
                minutes=self._get_market_slot_duration(future_time_slot, config).total_minutes())

    def create_future_markets(self, current_market_time_slot: DateTime,
                              config: "SimulationConfig") -> None:
        """Add sub dicts in order dictionaries for future market slots."""
        if not ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS:
            return
        self._create_future_markets(
            current_market_time_slot.add(minutes=config.slot_length.total_minutes()),
            current_market_time_slot.add(
                hours=ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS),
            config)

    @lock_market_action
    def bid(self, price: float, energy: float, buyer: str, buyer_origin: str,
            bid_id: Optional[str] = None,
            original_price: Optional[float] = None,
            adapt_price_with_fees: bool = True,
            add_to_history: bool = True,
            buyer_origin_id: Optional[str] = None,
            buyer_id: Optional[str] = None,
            attributes: Optional[Dict] = None,
            requirements: Optional[List[Dict]] = None,
            time_slot: Optional[DateTime] = None) -> Bid:
        """Call superclass bid and buffer returned bid object."""
        if not time_slot:
            raise FutureMarketException("time_slot parameter was not provided for bid "
                                        "method in future markets.")
        bid = super().bid(price=price, energy=energy, buyer=buyer, buyer_origin=buyer_origin,
                          bid_id=bid_id, original_price=original_price,
                          add_to_history=add_to_history,
                          adapt_price_with_fees=adapt_price_with_fees,
                          buyer_origin_id=buyer_origin_id, buyer_id=buyer_id,
                          attributes=attributes, requirements=requirements, time_slot=time_slot)
        return bid

    @lock_market_action
    def offer(self, price: float, energy: float, seller: str, seller_origin: str,
              offer_id: Optional[str] = None,
              original_price: Optional[float] = None,
              dispatch_event: bool = True,
              adapt_price_with_fees: bool = True,
              add_to_history: bool = True,
              seller_origin_id: Optional[str] = None,
              seller_id: Optional[str] = None,
              attributes: Optional[Dict] = None,
              requirements: Optional[List[Dict]] = None,
              time_slot: Optional[DateTime] = None) -> Offer:
        """Call superclass offer and buffer returned offer object."""
        if not time_slot:
            raise FutureMarketException("time_slot parameter was not provided for offer "
                                        "method in future markets.")
        offer = super().offer(price, energy, seller, seller_origin, offer_id, original_price,
                              dispatch_event, adapt_price_with_fees, add_to_history,
                              seller_origin_id, seller_id, attributes, requirements, time_slot)
        return offer

    @property
    def type_name(self):
        """Return the market type representation."""
        return "Future Market"
