import uuid
from collections import defaultdict, namedtuple
from logging import getLogger
from threading import Lock
from typing import Dict, List, Union  # noqa

from terminaltables.other_tables import SingleTable

from d3a.exceptions import MarketReadOnlyException, OfferNotFoundException, InvalidOffer


log = getLogger(__name__)


class Offer(namedtuple('Offer', ('id', 'price', 'energy', 'seller'))):
    def __str__(self):
        return "{{{s.id:.6s}}} [{s.seller}]: {s.energy} kWh @ {s.price}".format(s=self)


class Trade(namedtuple('Trade', ('offer', 'seller', 'buyer'))):
    def __str__(self):
        return "[{s.seller} -> {s.buyer}] {s.offer.energy} kWh @ {s.offer.price}".format(s=self)


class Market:
    def __init__(self, readonly=False):
        self.readonly = readonly
        self.offers = {}  # type: Dict[str, Offer]
        self.trades = []  # type: List[Trade]
        self.ious = defaultdict(lambda: defaultdict(int))
        self.accounting = defaultdict(int)
        self.offer_lock = Lock()
        self.trade_lock = Lock()

    def offer(self, energy: int, price: int, seller: str) -> Offer:
        if self.readonly:
            raise MarketReadOnlyException()
        if energy <= 0:
            raise InvalidOffer()
        offer = Offer(str(uuid.uuid4()), price, energy, seller)
        with self.offer_lock:
            self.offers[offer.id] = offer
            log.info("[OFFER][NEW] %s", offer)
        return offer

    def delete_offer(self, offer_or_id: Union[str, Offer]):
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        with self.offer_lock:
            bid = self.offers.pop(offer_or_id, None)
            if not bid:
                raise OfferNotFoundException()
            log.info("[OFFER][DEL] %s", bid)

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
        return trade

    def __repr__(self):  # pragma: no cover
        return "<Market offers: {}, trades: {}, energy: {}, price: {}>".format(
            len(self.offers),
            len(self.trades),
            sum(t.offer.energy for t in self.trades),
            sum(t.offer.price for t in self.trades)
        )

    def display(self):  # pragma: no cover
        if self.trades:
            print("Trades:")
            trade_table = [['From', 'To', 'kWh', 'Price']] + [
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
                pass
