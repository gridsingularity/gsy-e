import uuid
from collections import defaultdict, namedtuple
from logging import getLogger
from threading import Lock
from typing import Dict, List, Union  # noqa

from terminaltables.other_tables import SingleTable

from d3a.exceptions import InvalidOffer, MarketReadOnlyException, OfferNotFoundException
from d3a.models.events import MarketEvent


log = getLogger(__name__)


class Offer(namedtuple('Offer', ('id', 'price', 'energy', 'seller'))):
    def __str__(self):
        return "{{{s.id:.6s}}} [{s.seller}]: {s.energy} kWh @ {s.price}".format(s=self)


class Trade(namedtuple('Trade', ('offer', 'seller', 'buyer'))):
    def __str__(self):
        return "[{s.seller} -> {s.buyer}] {s.offer.energy} kWh @ {s.offer.price}".format(s=self)


class Market:
    def __init__(self, notification_listener=None, readonly=False):
        self.readonly = readonly
        # offer-id -> Offer
        self.offers = {}  # type: Dict[str, Offer]
        self.notification_listeners = []
        self.trades = []  # type: List[Trade]
        self.ious = defaultdict(lambda: defaultdict(int))
        self.accounting = defaultdict(int)
        self.offer_lock = Lock()
        self.trade_lock = Lock()
        if notification_listener:
            self.notification_listeners.append(notification_listener)

    def _notify_listeners(self, event, **kwargs):
        for listener in self.notification_listeners:
            listener(event, **kwargs)

    def offer(self, energy: int, price: int, seller: str) -> Offer:
        if self.readonly:
            raise MarketReadOnlyException()
        if energy <= 0:
            raise InvalidOffer()
        offer = Offer(str(uuid.uuid4()), price, energy, seller)
        with self.offer_lock:
            self.offers[offer.id] = offer
            log.info("[OFFER][NEW] %s", offer)
        self._notify_listeners(MarketEvent.OFFER, market=self, offer=offer)
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
        self._notify_listeners(MarketEvent.OFFER_DELETED, market=self, offer=offer)

    def accept_offer(self, offer_or_id: Union[str, Offer], buyer: str) -> Trade:
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        with self.offer_lock, self.trade_lock:
            offer = self.offers.pop(offer_or_id, None)
            if offer is None:
                raise OfferNotFoundException()
            trade = Trade(offer, offer.seller, buyer)
            self.trades.append(trade)
            log.info("[TRADE] %s", trade)
            self.accounting[offer.seller] -= offer.energy
            self.accounting[buyer] += offer.energy
            self.ious[buyer][offer.seller] += offer.price
        self._notify_listeners(MarketEvent.TRADE, market=self, trade=trade)
        return trade

    def __repr__(self):  # pragma: no cover
        return "<Market offers: {} (E: {} kWh V: {}) trades: {} (E: {} kWh, V: {})>".format(
            len(self.offers),
            sum(o.energy for o in self.offers.values()),
            sum(o.price for o in self.offers.values()),
            len(self.trades),
            sum(t.offer.energy for t in self.trades),
            sum(t.offer.price for t in self.trades)
        )

    def display(self):  # pragma: no cover
        if self.offers:
            print("Offers:")
            offer_table = [['From', 'kWh', 'Value']] + [
                [o.seller, o.energy, o.price]
                for o in self.offers.values()
            ]
            try:
                print(SingleTable(offer_table).table)
            except:
                # Could blow up with certain unicode characters
                pass
        if self.trades:
            print("Trades:")
            trade_table = [['From', 'To', 'kWh', 'Value']] + [
                [trade.seller, trade.buyer, trade.offer.energy, trade.offer.price]
                for trade in self.trades
            ]
            try:
                print(SingleTable(trade_table).table)
            except:
                # Could blow up with certain unicode characters
                pass
        if self.accounting:
            print("Energy accounting:")
            acct_table = [['Actor', 'Sum (kWh)']] + [
                [actor, energy]
                for actor, energy in self.accounting.items()
            ]
            try:
                print(SingleTable(acct_table).table)
            except:
                # Could blow up with certain unicode characters
                pass
