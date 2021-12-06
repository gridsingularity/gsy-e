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
from functools import wraps
from logging import getLogger
from threading import RLock
from typing import Dict, List, Union

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.data_classes import Offer, Trade, Bid
from gsy_framework.enums import SpotMarketTypeEnum
from numpy.random import random
from pendulum import DateTime

from gsy_e.constants import FLOATING_POINT_TOLERANCE, DATE_TIME_FORMAT
from gsy_e.gsy_e_core.device_registry import DeviceRegistry
from gsy_e.gsy_e_core.util import add_or_create_key, subtract_or_create_key
from gsy_e.models.market.grid_fees.base_model import GridFees
from gsy_e.models.market.grid_fees.constant_grid_fees import ConstantGridFees
from gsy_e.models.market.market_redis_connection import (
    MarketRedisEventSubscriber, MarketRedisEventPublisher,
    TwoSidedMarketRedisEventSubscriber)

log = getLogger(__name__)

GridFee = namedtuple("GridFee", ('grid_fee_percentage', 'grid_fee_const'))


RLOCK_MEMBER_NAME = "rlock"


def lock_market_action(function):
    @wraps(function)
    def wrapper(self, *args, **kwargs):
        # The market class needs to have an rlock member, that holds the recursive lock
        lock_object = getattr(self, RLOCK_MEMBER_NAME)
        if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
            return function(self, *args, **kwargs)
        else:
            with lock_object:
                return function(self, *args, **kwargs)
    return wrapper


class MarketBase:

    def __init__(self, time_slot=None, bc=None, notification_listener=None, readonly=False,
                 grid_fee_type=ConstSettings.MASettings.GRID_FEE_TYPE,
                 grid_fees: GridFee = None, name=None):
        self.name = name
        self.bc_interface = bc
        self.id = str(uuid.uuid4())
        self.time_slot = time_slot
        self.readonly = readonly
        # offer-id -> Offer
        self.offers = {}  # type: Dict[str, Offer]
        self.offer_history = []  # type: List[Offer]
        self.notification_listeners = []
        self.bids = {}  # type: Dict[str, Bid]
        self.bid_history = []  # type: List[Bid]
        self.trades = []  # type: List[Trade]
        self.const_fee_rate = None
        self.now = time_slot

        self._create_fee_handler(grid_fee_type, grid_fees)
        self.market_fee = 0
        # Store trades temporarily until bc event has fired
        self.traded_energy = {}
        self.min_trade_price = None
        self._avg_trade_price = None
        self.max_trade_price = None
        self.min_offer_price = None
        self._avg_offer_price = None
        self.max_offer_price = None
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
                if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.ONE_SIDED.value
                else TwoSidedMarketRedisEventSubscriber(self))
        setattr(self, RLOCK_MEMBER_NAME, RLock())

    @property
    def time_slot_str(self):
        """A string representation of the market slot."""
        return self.time_slot.format(DATE_TIME_FORMAT) if self.time_slot else None

    def _create_fee_handler(self, grid_fee_type, grid_fees):
        if not grid_fees:
            grid_fees = GridFee(grid_fee_percentage=0.0, grid_fee_const=0.0)
        if grid_fee_type == 1:
            if grid_fees.grid_fee_const is None or \
                    grid_fees.grid_fee_const <= 0.0:
                self.fee_class = ConstantGridFees(0.0)
            else:
                self.fee_class = ConstantGridFees(grid_fees.grid_fee_const)
            self.const_fee_rate = self.fee_class.grid_fee_rate
        else:
            if grid_fees.grid_fee_percentage is None or \
                    grid_fees.grid_fee_percentage <= 0.0:
                self.fee_class = GridFees(0.0)
            else:
                self.fee_class = GridFees(
                    grid_fees.grid_fee_percentage / 100
                )

    @property
    def _is_constant_fees(self):
        return isinstance(self.fee_class, ConstantGridFees)

    def orders_per_slot(self) -> Dict[str, Dict]:
        """Return all orders in the market per time slot."""
        bids = [bid.serializable_dict() for bid in self.bids.values()]
        offers = [offer.serializable_dict() for offer in self.offers.values()]
        return {self.time_slot_str: {"bids": bids, "offers": offers}}

    def add_listener(self, listener):
        self.notification_listeners.append(listener)

    def _notify_listeners(self, event, **kwargs):
        if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
            self.redis_publisher.publish_event(event, **kwargs)
        else:
            # Deliver notifications in random order to ensure fairness
            for listener in sorted(self.notification_listeners, key=lambda l: random()):
                listener(event, market_id=self.id, **kwargs)

    def _update_stats_after_trade(self, trade, offer_or_bid, already_tracked=False):
        # FIXME: The following updates need to be done in response to the BC event
        # TODO: For now event driven blockchain updates have been disabled in favor of a
        #  sequential approach, but once event handling is enabled this needs to be handled
        if not already_tracked:
            self.trades.append(trade)
            self.market_fee += trade.fee_price
        self._update_accumulated_trade_price_energy(trade)
        self.traded_energy = \
            add_or_create_key(self.traded_energy, trade.seller, offer_or_bid.energy)
        self.traded_energy = \
            subtract_or_create_key(self.traded_energy, trade.buyer, offer_or_bid.energy)
        self._update_min_max_avg_trade_prices(offer_or_bid.energy_rate)
        # Recalculate offer min/max price since offer was removed
        self._update_min_max_avg_offer_prices()

    def _update_accumulated_trade_price_energy(self, trade):
        self.accumulated_trade_price += trade.offer_bid.price
        self.accumulated_trade_energy += trade.offer_bid.energy

    def _update_min_max_avg_offer_prices(self):
        self._avg_offer_price = None
        offer_prices = [o.energy_rate for o in self.offers.values()]
        if offer_prices:
            self.min_offer_price = round(min(offer_prices), 4)
            self.max_offer_price = round(max(offer_prices), 4)

    def _update_min_max_avg_trade_prices(self, price):
        self.max_trade_price = round(max(self.max_trade_price, price), 4) if self.max_trade_price \
            else round(price, 4)
        self.min_trade_price = round(min(self.min_trade_price, price), 4) if self.min_trade_price \
            else round(price, 4)
        self._avg_trade_price = None
        self._avg_offer_price = None

    def __repr__(self):  # pragma: no cover
        return "<MarketBase{} offers: {} (E: {} kWh V: {}) trades: {} (E: {} kWh, V: {})>".format(
            " {}".format(self.time_slot_str),
            len(self.offers),
            sum(o.energy for o in self.offers.values()),
            sum(o.price for o in self.offers.values()),
            len(self.trades),
            self.accumulated_trade_energy,
            self.accumulated_trade_price
        )

    @staticmethod
    def sorting(offers_bids: Dict, reverse_order=False) -> List[Union[Bid, Offer]]:
        """Sort a list of bids or offers by their energy_rate attribute."""
        if reverse_order:
            # Sorted bids in descending order
            return list(reversed(sorted(
                offers_bids.values(),
                key=lambda obj: obj.energy_rate)))
        else:

            return sorted(offers_bids.values(),
                          key=lambda obj: obj.energy_rate,
                          reverse=reverse_order)

    @property
    def avg_offer_price(self):
        if self._avg_offer_price is None:
            price = sum(o.price for o in self.offers.values())
            energy = sum(o.energy for o in self.offers.values())
            self._avg_offer_price = round(price / energy, 4) if energy else 0
        return self._avg_offer_price

    @property
    def avg_trade_price(self):
        if self._avg_trade_price is None:
            price = self.accumulated_trade_price
            energy = self.accumulated_trade_energy
            self._avg_trade_price = round(price / energy, 4) if energy else 0
        return self._avg_trade_price

    @property
    def sorted_offers(self):
        return self.sorting(self.offers)

    @property
    def most_affordable_offers(self):
        cheapest_offer = self.sorted_offers[0]
        rate = cheapest_offer.energy_rate
        return [o for o in self.sorted_offers if
                abs(o.energy_rate - rate) < FLOATING_POINT_TOLERANCE]

    def update_clock(self, now: DateTime) -> None:
        """
        Update self.now member with the provided now DateTime
        Args:
            now: Datetime object

        Returns:

        """
        self.now = now

    def bought_energy(self, buyer):
        return sum(trade.offer_bid.energy for trade in self.trades if trade.buyer == buyer)

    def sold_energy(self, seller):
        return sum(trade.offer_bid.energy for trade in self.trades if trade.seller == seller)

    def total_spent(self, buyer):
        return sum(trade.offer_bid.price for trade in self.trades if trade.buyer == buyer)

    def total_earned(self, seller):
        return sum(trade.offer_bid.price for trade in self.trades if trade.seller == seller)

    @property
    def info(self):
        return {
            "name": self.name,
            "id": self.id,
            "start_time": self.time_slot_str,
            "duration_min": GlobalConfig.slot_length.minutes
        }

    def get_bids_offers_trades(self):
        return {
            "bids": [b.serializable_dict() for b in self.bid_history],
            "offers": [o.serializable_dict() for o in self.offer_history],
            "trades": [t.serializable_dict() for t in self.trades]
        }
