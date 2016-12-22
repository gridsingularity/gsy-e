import random
import uuid
from collections import defaultdict, namedtuple
from logging import getLogger
from threading import Lock
from typing import Dict, List, Set, Union  # noqa

import sys

from pendulum.pendulum import Pendulum
from terminaltables.other_tables import SingleTable

from d3a.exceptions import InvalidOffer, MarketReadOnlyException, OfferNotFoundException
from d3a.models.events import MarketEvent, OfferEvent


log = getLogger(__name__)


class Offer:
    def __init__(self, id, price, energy, seller):
        self.id = str(id)
        self.price = price
        self.energy = energy
        self.seller = seller
        self._listeners = defaultdict(set)  # type: Dict[OfferEvent, Set[callable]]

    def __repr__(self):
        return "<Offer('{s.id!s:.6s}', '{s.energy} kWh@{s.price}', '{s.seller}'>".format(s=self)

    def __str__(self):
        return "{{{s.id!s:.6s}}} [{s.seller}]: {s.energy} kWh @ {s.price}".format(s=self)

    def add_listener(self, event: Union[OfferEvent, List[OfferEvent]], listener):
        if isinstance(event, (tuple, list)):
            for ev in event:
                self.add_listener(ev, listener)
        else:
            self._listeners[event].add(listener)

    def _call_listeners(self, event: OfferEvent, **kwargs):
        # Call listeners in random order to ensure fairness
        for listener in sorted(self._listeners[event], key=lambda l: random.random()):
            listener(**kwargs, offer=self)

    # XXX: This might be unreliable - decide after testing
    def __del__(self):
        self._call_listeners(OfferEvent.DELETED)

    def _traded(self, trade: 'Trade', market: 'Market'):
        """
        Called by `Market` to inform listeners about the trade
        """
        self._call_listeners(OfferEvent.ACCEPTED, market=market, trade=trade)


class Trade(namedtuple('Trade', ('id', 'time', 'offer', 'seller', 'buyer'))):
    def __str__(self):
        return (
            "{{{s.id!s:.6s}}} [{s.seller} -> {s.buyer}] "
            "{s.offer.energy} kWh @ {s.offer.price}".format(s=self)
        )


class Market:
    def __init__(self, time_slot=None, area=None, notification_listener=None, readonly=False):
        self.area = area
        self.time_slot = time_slot
        self.readonly = readonly
        # offer-id -> Offer
        self.offers = {}  # type: Dict[str, Offer]
        self.notification_listeners = []
        self.trades = []  # type: List[Trade]
        self.ious = defaultdict(lambda: defaultdict(int))
        self.accounting = defaultdict(int)
        self.min_trade_price = sys.maxsize
        self.max_trade_price = 0
        self.offer_lock = Lock()
        self.trade_lock = Lock()
        if notification_listener:
            self.notification_listeners.append(notification_listener)

    def add_listener(self, listener):
        self.notification_listeners.append(listener)

    def _notify_listeners(self, event, **kwargs):
        # Deliver notifications in random order to ensure fairness
        for listener in sorted(self.notification_listeners, key=lambda l: random.random()):
            listener(event, market=self, **kwargs)

    def offer(self, energy: int, price: int, seller: str) -> Offer:
        if self.readonly:
            raise MarketReadOnlyException()
        if energy <= 0:
            raise InvalidOffer()
        offer = Offer(str(uuid.uuid4()), price, energy, seller)
        with self.offer_lock:
            self.offers[offer.id] = offer
            log.info("[OFFER][NEW] %s", offer)
        self._notify_listeners(MarketEvent.OFFER, offer=offer)
        return offer

    def delete_offer(self, offer_or_id: Union[str, Offer]):
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        with self.offer_lock:
            offer = self.offers.pop(offer_or_id, None)
            if not offer:
                raise OfferNotFoundException()
            log.info("[OFFER][DEL] %s", offer)
        self._notify_listeners(MarketEvent.OFFER_DELETED, offer=offer)

    def accept_offer(self, offer_or_id: Union[str, Offer], buyer: str,
                     time: Pendulum = None) -> Trade:
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        with self.offer_lock, self.trade_lock:
            offer = self.offers.pop(offer_or_id, None)
            if offer is None:
                raise OfferNotFoundException()
            if time is None:
                time = self._now
            trade = Trade(str(uuid.uuid4()), time, offer, offer.seller, buyer)
            self.trades.append(trade)
            log.warning("[TRADE] %s", trade)
            self.accounting[offer.seller] -= offer.energy
            self.accounting[buyer] += offer.energy
            self.ious[buyer][offer.seller] += offer.price
            price = offer.price / offer.energy
            self.max_trade_price = max(self.max_trade_price, price)
            self.min_trade_price = min(self.min_trade_price, price)
        offer._traded(trade, self)
        self._notify_listeners(MarketEvent.TRADE, trade=trade)
        return trade

    def __repr__(self):  # pragma: no cover
        return "<Market{} offers: {} (E: {} kWh V: {}) trades: {} (E: {} kWh, V: {})>".format(
            " {:%H:%M}".format(self.time_slot) if self.time_slot else "",
            len(self.offers),
            sum(o.energy for o in self.offers.values()),
            sum(o.price for o in self.offers.values()),
            len(self.trades),
            sum(t.offer.energy for t in self.trades),
            sum(t.offer.price for t in self.trades)
        )

    @property
    def avg_offer_price(self):
        with self.offer_lock:
            price = sum(o.price for o in self.offers.values())
            energy = sum(o.energy for o in self.offers.values())
        return (price / energy) if energy else 0

    @property
    def avg_trade_price(self):
        with self.trade_lock:
            price = sum(t.offer.price for t in self.trades)
            energy = sum(t.offer.energy for t in self.trades)
        return (price / energy) if energy else 0

    @property
    def sorted_offers(self):
        return sorted(self.offers.values(), key=lambda o: o.price / o.energy)

    @property
    def _now(self):
        if self.area:
            return self.area.get_now()
        log.error("No area available. Using real system time!")
        return Pendulum.now()

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
            except:
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
            except:
                # Could blow up with certain unicode characters
                pass
        if self.accounting:
            out.append("Energy accounting:")
            acct_table = [['Actor', 'Sum (kWh)']] + [
                [actor, energy]
                for actor, energy in self.accounting.items()
            ]
            try:
                out.append(SingleTable(acct_table).table)
            except:
                # Could blow up with certain unicode characters
                pass
        return "\n".join(out)
