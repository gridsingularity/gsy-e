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

import uuid
import sys
from logging import getLogger
from typing import Dict, List  # noqa
from numpy.random import random
from collections import namedtuple
from pendulum import DateTime
from functools import wraps
from threading import RLock

from d3a.d3a_core.device_registry import DeviceRegistry
from d3a.constants import FLOATING_POINT_TOLERANCE, DATE_TIME_FORMAT
from d3a.models.market.market_structures import Offer, Trade, Bid  # noqa
from d3a.d3a_core.util import add_or_create_key, subtract_or_create_key
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from d3a.models.market.market_redis_connection import MarketRedisEventSubscriber, \
    MarketRedisEventPublisher, TwoSidedMarketRedisEventSubscriber

log = getLogger(__name__)

TransferFees = namedtuple("TransferFees", ('transfer_fee_pct', 'transfer_fee_const'))


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


class Market:

    def __init__(self, time_slot=None, bc=None, notification_listener=None, readonly=False,
                 transfer_fees: TransferFees = None, name=None):
        self.name = name
        self.bc = bc
        self.id = str(uuid.uuid4())
        self.time_slot = time_slot
        self.time_slot_str = time_slot.format(DATE_TIME_FORMAT) \
            if self.time_slot is not None \
            else None
        self.readonly = readonly
        # offer-id -> Offer
        self.offers = {}  # type: Dict[str, Offer]
        self.offer_history = []  # type: List[Offer]
        self.notification_listeners = []
        self.bids = {}  # type: Dict[str, Bid]
        self.bid_history = []  # type: List[Bid]
        self.trades = []  # type: List[Trade]
        self.transfer_fee_ratio = transfer_fees.transfer_fee_pct / 100 \
            if transfer_fees is not None else 0
        self.transfer_fee_const = transfer_fees.transfer_fee_const \
            if transfer_fees is not None else 0
        self.market_fee = 0
        # Store trades temporarily until bc event has fired
        self.traded_energy = {}
        self.accumulated_actual_energy_agg = {}
        self.min_trade_price = sys.maxsize
        self._avg_trade_price = None
        self.max_trade_price = 0
        self.min_offer_price = sys.maxsize
        self._avg_offer_price = None
        self.max_offer_price = 0
        self.accumulated_trade_price = 0
        self.accumulated_trade_energy = 0
        if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
            self.redis_publisher = MarketRedisEventPublisher(self.id)
        elif notification_listener:
            self.notification_listeners.append(notification_listener)
        self.current_tick = 0
        self.device_registry = DeviceRegistry.REGISTRY
        if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
            self.redis_api = MarketRedisEventSubscriber(self) \
                if ConstSettings.IAASettings.MARKET_TYPE == 1 \
                else TwoSidedMarketRedisEventSubscriber(self)
        setattr(self, RLOCK_MEMBER_NAME, RLock())

    def add_listener(self, listener):
        self.notification_listeners.append(listener)

    def _notify_listeners(self, event, **kwargs):
        if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
            self.redis_publisher.publish_event(event, **kwargs)
        else:
            # Deliver notifications in random order to ensure fairness
            for listener in sorted(self.notification_listeners, key=lambda l: random()):
                listener(event, market_id=self.id, **kwargs)

    def _update_stats_after_trade(self, trade, offer, buyer, already_tracked=False):
        # FIXME: The following updates need to be done in response to the BC event
        # TODO: For now event driven blockchain updates have been disabled in favor of a
        # sequential approach, but once event handling is enabled this needs to be handled
        if not already_tracked:
            self.trades.append(trade)
        self.market_fee += trade.fee_price
        self._update_accumulated_trade_price_energy(trade)
        self.traded_energy = add_or_create_key(self.traded_energy, offer.seller, offer.energy)
        self.traded_energy = subtract_or_create_key(self.traded_energy, buyer, offer.energy)
        self._update_min_max_avg_trade_prices(offer.price / offer.energy)
        # Recalculate offer min/max price since offer was removed
        self._update_min_max_avg_offer_prices()

    def _update_accumulated_trade_price_energy(self, trade):
        self.accumulated_trade_price += trade.offer.price
        self.accumulated_trade_energy += trade.offer.energy

    def _update_min_max_avg_offer_prices(self):
        self._avg_offer_price = None
        offer_prices = [o.price / o.energy for o in self.offers.values()]
        if offer_prices:
            self.min_offer_price = round(min(offer_prices), 4)
            self.max_offer_price = round(max(offer_prices), 4)

    def _update_min_max_avg_trade_prices(self, price):
        self.max_trade_price = round(max(self.max_trade_price, price), 4)
        self.min_trade_price = round(min(self.min_trade_price, price), 4)
        self._avg_trade_price = None
        self._avg_offer_price = None

    def __repr__(self):  # pragma: no cover
        return "<Market{} offers: {} (E: {} kWh V: {}) trades: {} (E: {} kWh, V: {})>".format(
            " {}".format(self.time_slot_str),
            len(self.offers),
            sum(o.energy for o in self.offers.values()),
            sum(o.price for o in self.offers.values()),
            len(self.trades),
            self.accumulated_trade_energy,
            self.accumulated_trade_price
        )

    @staticmethod
    def sorting(obj, reverse_order=False):
        if reverse_order:
            # Sorted bids in descending order
            return list(reversed(sorted(
                obj.values(),
                key=lambda b: b.price / b.energy)))

        else:
            # Sorted bids in ascending order
            return list(sorted(
                obj.values(),
                key=lambda b: b.price / b.energy))

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
        rate = cheapest_offer.price / cheapest_offer.energy
        return [o for o in self.sorted_offers if
                abs(o.price / o.energy - rate) < FLOATING_POINT_TOLERANCE]

    def update_clock(self, current_tick):
        self.current_tick = current_tick

    @property
    def now(self) -> DateTime:
        return GlobalConfig.start_date.add(
            seconds=GlobalConfig.tick_length.seconds * self.current_tick)

    def set_actual_energy(self, time, reporter, value):
        if reporter in self.accumulated_actual_energy_agg:
            self.accumulated_actual_energy_agg[reporter] += value
        else:
            self.accumulated_actual_energy_agg[reporter] = value

    @property
    def actual_energy_agg(self):
        return self.accumulated_actual_energy_agg

    def bought_energy(self, buyer):
        return sum(trade.offer.energy for trade in self.trades if trade.buyer == buyer)

    def sold_energy(self, seller):
        return sum(trade.offer.energy for trade in self.trades if trade.offer.seller == seller)

    def total_spent(self, buyer):
        return sum(trade.offer.price for trade in self.trades if trade.buyer == buyer)

    def total_earned(self, seller):
        return sum(trade.offer.price for trade in self.trades if trade.seller == seller)

    @property
    def info(self):
        return {
            "name": self.name,
            "id": self.id,
            "start_time": self.time_slot_str,
            "duration_min": GlobalConfig.slot_length.minutes
        }
