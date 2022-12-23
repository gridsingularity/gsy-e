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
from gsy_framework.data_classes import Bid, Offer, Trade, TraderDetails
from gsy_framework.utils import is_time_slot_in_simulation_duration
from pendulum import DateTime, duration

from gsy_e.gsy_e_core.blockchain_interface import NonBlockchainInterface
from gsy_e.models.market import GridFee, lock_market_action, MarketSlotParams
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
    def slot_bid_mapping(self) -> Dict[DateTime, List[Bid]]:
        """Return the {time_slot: [bids_list]} mapping."""
        return self.bids.slot_order_mapping

    @property
    def slot_offer_mapping(self) -> Dict[DateTime, List[Offer]]:
        """Return the {time_slot: [offers_list]} mapping."""
        return self.offers.slot_order_mapping

    @property
    def slot_trade_mapping(self) -> Dict[DateTime, List[Trade]]:
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
    def _calculate_closing_time(delivery_time: DateTime) -> DateTime:
        """
        Closing time of the market. Uses as basis the delivery time in order to calculate it.
        """
        return delivery_time

    @staticmethod
    def _get_start_time(current_time: DateTime, config: "SimulationConfig") -> DateTime:
        """Return time when the market block starts."""
        return current_time.add(minutes=config.slot_length.total_minutes())

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        """Return time when the market block ends."""
        return current_time.add(
            hours=ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS)

    def _create_future_market_slots(
            self, config: "SimulationConfig", current_market_time_slot: DateTime
    ) -> List[DateTime]:
        future_time_slot = self._get_start_time(current_market_time_slot, config)
        end_time = self._get_end_time(current_market_time_slot)
        created_market_slots = []
        while future_time_slot <= end_time:
            market_close_time = self._calculate_closing_time(future_time_slot)
            if (future_time_slot not in self.slot_bid_mapping and
                    is_time_slot_in_simulation_duration(future_time_slot, config) and
                    market_close_time > current_market_time_slot):
                self.bids.slot_order_mapping[future_time_slot] = []
                self.offers.slot_order_mapping[future_time_slot] = []
                created_market_slots.append(future_time_slot)
            future_time_slot = (
                future_time_slot + self._get_market_slot_duration(config))
        return created_market_slots

    def create_future_market_slots(self, current_market_time_slot: DateTime,
                                   config: "SimulationConfig") -> List[DateTime]:
        """Add sub dicts in order dictionaries for future market slots."""
        if not ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS:
            return []
        created_future_slots = self._create_future_market_slots(config, current_market_time_slot)

        self.set_open_market_slot_parameters(current_market_time_slot, created_future_slots)
        return created_future_slots

    @lock_market_action
    def bid(self, price: float, energy: float, buyer: TraderDetails,
            bid_id: Optional[str] = None,
            original_price: Optional[float] = None,
            adapt_price_with_fees: bool = True,
            add_to_history: bool = True,
            dispatch_event: bool = True,
            time_slot: Optional[DateTime] = None) -> Bid:
        """Call superclass bid and buffer returned bid object."""
        if not time_slot:
            raise FutureMarketException("time_slot parameter was not provided for bid "
                                        "method in future markets.")
        bid = super().bid(price=price, energy=energy, buyer=buyer,
                          bid_id=bid_id, original_price=original_price,
                          add_to_history=add_to_history,
                          adapt_price_with_fees=adapt_price_with_fees,
                          dispatch_event=dispatch_event,
                          time_slot=time_slot)
        return bid

    @lock_market_action
    def offer(self, price: float, energy: float, seller: TraderDetails,
              offer_id: Optional[str] = None,
              original_price: Optional[float] = None,
              dispatch_event: bool = True,
              adapt_price_with_fees: bool = True,
              add_to_history: bool = True,
              time_slot: Optional[DateTime] = None) -> Offer:
        """Call superclass offer and buffer returned offer object."""
        if not time_slot:
            raise FutureMarketException("time_slot parameter was not provided for offer "
                                        "method in future markets.")
        offer = super().offer(price, energy, seller, offer_id, original_price,
                              dispatch_event, adapt_price_with_fees, add_to_history,
                              time_slot)
        return offer

    @property
    def type_name(self):
        """Return the market type representation."""
        return "Future Market"

    def set_open_market_slot_parameters(
            self, current_market_slot: DateTime, created_market_slots: List[DateTime]):
        """Update the parameters of the newly opened market slots."""
        for market_slot in created_market_slots:
            if market_slot in self._open_market_slot_parameters:
                continue

            self._open_market_slot_parameters[market_slot] = MarketSlotParams(
                delivery_start_time=market_slot,
                delivery_end_time=(
                        market_slot + self._get_market_slot_duration(None)),
                opening_time=market_slot - duration(
                    hours=ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS),
                closing_time=self._calculate_closing_time(market_slot)
            )
