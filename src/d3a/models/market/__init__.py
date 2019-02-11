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
import random
import uuid
from collections import defaultdict
from logging import getLogger
from typing import Dict, List  # noqa
import sys

from pendulum import DateTime
from terminaltables.other_tables import SingleTable

from d3a.constants import TIME_ZONE, DATE_TIME_FORMAT
from d3a.d3a_core.device_registry import DeviceRegistry


log = getLogger(__name__)


OFFER_PRICE_THRESHOLD = 0.00001


class Market:
    def __init__(self, time_slot=None, area=None, notification_listener=None, readonly=False):
        self.area = area
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
        # Store trades temporarily until bc event has fired
        self.ious = defaultdict(lambda: defaultdict(int))
        self.traded_energy = defaultdict(int)
        # Store actual energy consumption in a nested dict in the form of
        # Timestamp -> Actor -> Value
        self.actual_energy = defaultdict(
            lambda: defaultdict(int))  # type: Dict[DateTime, Dict[str, float]]
        self.accumulated_actual_energy_agg = {}
        self.min_trade_price = sys.maxsize
        self._avg_trade_price = None
        self.max_trade_price = 0
        self.min_offer_price = sys.maxsize
        self._avg_offer_price = None
        self.max_offer_price = 0
        self._sorted_offers = []
        self.accumulated_trade_price = 0
        self.accumulated_trade_energy = 0
        if notification_listener:
            self.notification_listeners.append(notification_listener)

        self.device_registry = DeviceRegistry.REGISTRY

    def add_listener(self, listener):
        self.notification_listeners.append(listener)

    def _notify_listeners(self, event, **kwargs):
        # Deliver notifications in random order to ensure fairness
        for listener in sorted(self.notification_listeners, key=lambda l: random.random()):
            listener(event, market_id=self.id, **kwargs)

    def _update_stats_after_trade(self, trade, offer, buyer, already_tracked=False):
        # FIXME: The following updates need to be done in response to the BC event
        # TODO: For now event driven blockchain updates have been disabled in favor of a
        # sequential approach, but once event handling is enabled this needs to be handled
        if not already_tracked:
            self.trades.append(trade)
        self._update_accumulated_trade_price_energy(trade)
        self.traded_energy[offer.seller] += offer.energy
        self.traded_energy[buyer] -= offer.energy
        self.ious[buyer][offer.seller] += offer.price
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
        return self._sorted_offers

    @property
    def most_affordable_offers(self):
        cheapest_offer = self.sorted_offers[0]
        rate = cheapest_offer.price / cheapest_offer.energy
        return [o for o in self.sorted_offers if
                abs(o.price / o.energy - rate) < OFFER_PRICE_THRESHOLD]

    @property
    def _now(self):
        if self.area:
            return self.area.now
        log.error("No area available. Using real system time!")
        return DateTime.now(tz=TIME_ZONE)

    def set_actual_energy(self, time, reporter, value):
        self.actual_energy[time][reporter] += value
        if reporter in self.accumulated_actual_energy_agg:
            self.accumulated_actual_energy_agg[reporter] += value
        else:
            self.accumulated_actual_energy_agg[reporter] = value

    @property
    def actual_energy_agg(self):
        return self.accumulated_actual_energy_agg

    def display(self):  # pragma: no cover
        out = []
        if self.offers:
            out.append("Offers:")
            offer_table = [['From', 'kWh', 'Value']] + [
                [o.seller, o.energy, o.price]
                for o in self.offers.values()
            ]
            try:
                out.append(SingleTable(offer_table).table)
            except UnicodeError:
                # Could blow up with certain unicode characters
                pass
        if self.trades:
            out.append("Trades:")
            trade_table = [['From', 'To', 'kWh', 'Value']] + [
                [trade.seller, trade.buyer, trade.offer.energy, trade.offer.price]
                for trade in self.trades
            ]
            try:
                out.append(SingleTable(trade_table).table)
            except UnicodeError:
                # Could blow up with certain unicode characters
                pass
        if self.traded_energy:
            out.append("Traded Energy:")
            acct_table = [['Actor', 'Sum (kWh)']] + [
                [actor, energy]
                for actor, energy in self.traded_energy.items()
            ]
            try:
                out.append(SingleTable(acct_table).table)
            except UnicodeError:
                # Could blow up with certain unicode characters
                pass
        return "\n".join(out)

    def bought_energy(self, buyer):
        return sum(trade.offer.energy for trade in self.trades if trade.buyer == buyer)

    def sold_energy(self, seller):
        return sum(trade.offer.energy for trade in self.trades if trade.offer.seller == seller)

    def total_spent(self, buyer):
        return sum(trade.offer.price for trade in self.trades if trade.buyer == buyer)

    def total_earned(self, seller):
        return sum(trade.offer.price for trade in self.trades if trade.seller == seller)
