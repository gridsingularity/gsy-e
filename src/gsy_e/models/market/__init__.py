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

import uuid
from collections import namedtuple
from dataclasses import dataclass
from functools import wraps
from logging import getLogger
from threading import RLock
from typing import Dict, List, Union, Optional, Callable, TYPE_CHECKING

from gsy_framework.constants_limits import (
    ConstSettings,
    GlobalConfig,
    FLOATING_POINT_TOLERANCE,
    DATE_TIME_FORMAT,
)
from gsy_framework.data_classes import Offer, Trade, Bid
from numpy.random import random
from pendulum import DateTime, duration

from gsy_e.gsy_e_core.device_registry import DeviceRegistry
from gsy_e.gsy_e_core.util import (
    add_or_create_key,
    subtract_or_create_key,
    is_one_sided_market_simulation,
)
from gsy_e.models.market.grid_fees.base_model import GridFees
from gsy_e.models.market.grid_fees.constant_grid_fees import ConstantGridFees
from gsy_e.models.market.market_redis_connection import (
    MarketRedisEventSubscriber,
    MarketRedisEventPublisher,
    TwoSidedMarketRedisEventSubscriber,
)

if TYPE_CHECKING:
    from gsy_e.models.config import SimulationConfig

log = getLogger(__name__)

GridFee = namedtuple("GridFee", ("grid_fee_percentage", "grid_fee_const"))


RLOCK_MEMBER_NAME = "rlock"


def lock_market_action(function):
    """Handle the locking behavior of a market."""

    @wraps(function)
    def wrapper(self, *args, **kwargs):
        # The market class needs to have an rlock member, that holds the recursive lock
        lock_object = getattr(self, RLOCK_MEMBER_NAME)
        if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
            return function(self, *args, **kwargs)

        with lock_object:
            return function(self, *args, **kwargs)

    return wrapper


@dataclass(frozen=True)
class MarketSlotParams:
    """Parameters that describe a market slot."""

    opening_time: DateTime
    closing_time: DateTime
    delivery_start_time: DateTime
    delivery_end_time: DateTime

    def __post_init__(self):
        assert self.delivery_end_time > self.delivery_start_time
        assert self.closing_time <= self.delivery_start_time
        assert self.closing_time > self.opening_time


class MarketBase:  # pylint: disable=too-many-instance-attributes
    """
    Hold the common energy market models behaviors and states.
    Energy markets are commodity markets that deal specifically with the trade
    and supply/demand of energy in a specific time slot.
    Market classes keep track of the orders placed, grid fees and trades in the market.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        time_slot: Optional[DateTime] = None,
        bc=None,
        notification_listener: Optional[Callable] = None,
        readonly: bool = False,
        grid_fee_type: int = ConstSettings.MASettings.GRID_FEE_TYPE,
        grid_fees: Optional[GridFee] = None,
        name: Optional[str] = None,
    ):
        self.name = name
        self.bc_interface = bc
        self.id = str(uuid.uuid4())
        self.time_slot = time_slot
        self.readonly = readonly
        # offer-id -> Offer
        self.offers: Dict[str, Offer] = {}
        self.offer_history: List[Offer] = []
        self.notification_listeners: List[Callable] = []
        self.bids: Dict[str, Bid] = {}
        self.bid_history: List[Bid] = []
        self.trades: List[Trade] = []
        self.const_fee_rate: Optional[float] = None
        self.now: DateTime = time_slot

        self._create_fee_handler(grid_fee_type, grid_fees)
        self.market_fee: float = 0
        # Store trades temporarily until bc event has fired
        self.traded_energy = {}
        self.min_trade_price = None
        self._avg_trade_price = None
        self.max_trade_price = None
        self.accumulated_trade_price = 0
        self.accumulated_trade_energy = 0
        if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
            self.redis_publisher = MarketRedisEventPublisher(self.id)
        elif notification_listener:
            self.notification_listeners.append(notification_listener)

        self.device_registry = DeviceRegistry.REGISTRY
        if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
            self.redis_api = (
                MarketRedisEventSubscriber(self)
                if is_one_sided_market_simulation()
                else TwoSidedMarketRedisEventSubscriber(self)
            )
        setattr(self, RLOCK_MEMBER_NAME, RLock())

        self._open_market_slot_parameters: Dict[DateTime, MarketSlotParams] = {}
        self.no_new_order = True

    @property
    def time_slot_str(self):
        """A string representation of the market slot."""
        return self.time_slot.format(DATE_TIME_FORMAT) if self.time_slot else None

    @property
    def info(self) -> Dict:
        """Return information about the market instance."""
        return {
            "name": self.name,
            "id": self.id,
            "start_time": self.time_slot_str,
            "duration_min": GlobalConfig.slot_length.minutes,
            "time_slots": [self.time_slot_str],  # Use a list for compatibility with future markets
            "type_name": self.type_name,
        }

    @property
    def type_name(self) -> str:
        """Return the market type representation."""
        return "Market"

    @property
    def avg_trade_price(self) -> float:
        """Update and return the average trade price in the current market."""

        if self._avg_trade_price is None:
            price = self.accumulated_trade_price
            energy = self.accumulated_trade_energy
            self._avg_trade_price = round(price / energy, 4) if energy else 0
        return self._avg_trade_price

    @property
    def sorted_offers(self):
        """Sort the offers using the self.sorting method."""

        return self.sorting(self.offers)

    @property
    def most_affordable_offers(self):
        """Return the offers with the least energy_rate value."""
        cheapest_offer = self.sorted_offers[0]
        rate = cheapest_offer.energy_rate
        return [
            o for o in self.sorted_offers if abs(o.energy_rate - rate) < FLOATING_POINT_TOLERANCE
        ]

    def _create_fee_handler(self, grid_fee_type: int, grid_fees: GridFee) -> None:
        if not grid_fees:
            grid_fees = GridFee(grid_fee_percentage=0.0, grid_fee_const=0.0)
        if grid_fee_type == 1:
            if grid_fees.grid_fee_const is None or grid_fees.grid_fee_const <= 0.0:
                self.fee_class = ConstantGridFees(0.0)
            else:
                self.fee_class = ConstantGridFees(grid_fees.grid_fee_const)
            self.const_fee_rate = self.fee_class.grid_fee_rate
        else:
            if grid_fees.grid_fee_percentage is None or grid_fees.grid_fee_percentage <= 0.0:
                self.fee_class = GridFees(0.0)
            else:
                self.fee_class = GridFees(grid_fees.grid_fee_percentage / 100)

    @property
    def _is_constant_fees(self) -> bool:
        """Return True if this market adopts the constant grid fees model."""
        return isinstance(self.fee_class, ConstantGridFees)

    def orders_per_slot(self) -> Dict[str, Dict]:
        """Return all orders in the market per time slot."""
        bids = [bid.serializable_dict() for bid in self.bids.values()]
        offers = [offer.serializable_dict() for offer in self.offers.values()]
        return {self.time_slot_str: {"bids": bids, "offers": offers}}

    def add_listener(self, listener: Callable):
        """Append a callable function to the notification_listeners list."""
        self.notification_listeners.append(listener)

    def _notify_listeners(self, event, **kwargs):
        """Invoke the notification_listeners to dispatch the passed event argument."""

        if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
            self.redis_publisher.publish_event(event, **kwargs)
        else:
            # Deliver notifications in random order to ensure fairness
            for listener in sorted(self.notification_listeners, key=lambda inp: random()):
                listener(event, market_id=self.id, **kwargs)

    def _update_stats_after_trade(self, trade: Trade, order: Union[Offer, Bid]) -> None:
        """Update the instance state in response to an occurring trade."""
        self.trades.append(trade)
        self.market_fee += trade.fee_price
        self._update_accumulated_trade_price_energy(trade)
        self.traded_energy = add_or_create_key(self.traded_energy, trade.seller.name, order.energy)
        self.traded_energy = subtract_or_create_key(
            self.traded_energy, trade.buyer.name, order.energy
        )
        self._update_min_max_avg_trade_prices(order.energy_rate)

    def _update_accumulated_trade_price_energy(self, trade: Trade):
        self.accumulated_trade_price += trade.trade_price
        self.accumulated_trade_energy += trade.traded_energy

    def _update_min_max_avg_trade_prices(self, price):
        self.max_trade_price = (
            round(max(self.max_trade_price, price), 4) if self.max_trade_price else round(price, 4)
        )
        self.min_trade_price = (
            round(min(self.min_trade_price, price), 4) if self.min_trade_price else round(price, 4)
        )
        self._avg_trade_price = None

    def __repr__(self):
        return (
            f"<MarketBase {self.time_slot_str} offers: {len(self.offers)}"
            f" (E: {sum(o.energy for o in self.offers.values())} kWh"
            f" V: {sum(o.price for o in self.offers.values())})"
            f" trades: {len(self.trades)} (E: {self.accumulated_trade_energy} kWh,"
            f" V: {self.accumulated_trade_price})>"
        )

    @staticmethod
    def sorting(offers_bids: Dict, reverse_order=False) -> List[Union[Bid, Offer]]:
        """Sort a list of bids or offers by their energy_rate attribute."""
        if reverse_order:
            # Sorted bids in descending order
            return list(reversed(sorted(offers_bids.values(), key=lambda obj: obj.energy_rate)))
        return sorted(offers_bids.values(), key=lambda obj: obj.energy_rate, reverse=reverse_order)

    def update_clock(self, now: DateTime) -> None:
        """
        Update self.now member with the provided now DateTime
        Args:
            now: Datetime object

        Returns:

        """
        self.now = now

    def bought_energy(self, buyer: str) -> float:
        """Return the aggregated bought energy value by the passed-in buyer."""

        return sum(trade.traded_energy for trade in self.trades if trade.buyer.name == buyer)

    def sold_energy(self, seller: str) -> float:
        """Return the aggregated sold energy value by the passed-in seller."""

        return sum(trade.traded_energy for trade in self.trades if trade.seller.name == seller)

    def total_spent(self, buyer: str) -> float:
        """Return the aggregated money spent by the passed-in buyer."""

        return sum(trade.trade_price for trade in self.trades if trade.buyer.name == buyer)

    def total_earned(self, seller: str) -> float:
        """Return the aggregated money earned by the passed-in seller."""
        return sum(trade.trade_price for trade in self.trades if trade.seller.name == seller)

    @staticmethod
    def _calculate_closing_time(delivery_time: DateTime) -> DateTime:
        """
        Closing time of the market. Uses as basis the delivery time in order to calculate it.
        """
        return delivery_time + GlobalConfig.slot_length

    @staticmethod
    def _get_market_slot_duration(config: Optional["SimulationConfig"]) -> duration:
        if config:
            return config.slot_length
        return GlobalConfig.slot_length

    def get_market_parameters_for_market_slot(self, market_slot: DateTime) -> MarketSlotParams:
        """Retrieve the parameters for the selected market slot."""
        return self._open_market_slot_parameters.get(market_slot)

    @property
    def open_market_slot_info(self) -> Dict[DateTime, MarketSlotParams]:
        """Retrieve market slot parameters"""
        return self._open_market_slot_parameters

    def set_open_market_slot_parameters(
        self, current_market_slot: DateTime, created_market_slots: Optional[List[DateTime]]
    ):
        """Update the parameters of the newly opened market slots."""
        for market_slot in created_market_slots:
            if market_slot in self._open_market_slot_parameters:
                continue

            self._open_market_slot_parameters[market_slot] = MarketSlotParams(
                delivery_start_time=self._calculate_closing_time(market_slot),
                delivery_end_time=self._calculate_closing_time(market_slot)
                + self._get_market_slot_duration(None),
                opening_time=current_market_slot,
                closing_time=self._calculate_closing_time(market_slot),
            )
