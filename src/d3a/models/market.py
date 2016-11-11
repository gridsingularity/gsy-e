import uuid
from collections import defaultdict, namedtuple
from logging import getLogger
from threading import Lock
from typing import Dict, List, Union  # noqa

from terminaltables.other_tables import SingleTable

from d3a.exceptions import MarketReadOnlyException, BidNotFoundException, InvalidBid


log = getLogger(__name__)


class Bid(namedtuple('Bid', ('id', 'price', 'energy', 'seller'))):
    def __str__(self):
        return "{{{s.id:.6s}}} [{s.seller}]: {s.energy} kWh @ {s.price}".format(s=self)


class Trade(namedtuple('Trade', ('bid', 'seller', 'buyer'))):
    def __str__(self):
        return "[{s.seller} -> {s.buyer}] {s.bid.energy} kWh @ {s.bid.price}".format(s=self)


class Market:
    def __init__(self, readonly=False):
        self.readonly = readonly
        self.bids = {}  # type: Dict[str, Bid]
        self.trades = []  # type: List[Trade]
        self.ious = defaultdict(lambda: defaultdict(int))
        self.accounting = defaultdict(int)
        self.bid_lock = Lock()
        self.trade_lock = Lock()

    def bid(self, energy: int, price: int, seller: str) -> Bid:
        if self.readonly:
            raise MarketReadOnlyException()
        if energy <= 0:
            raise InvalidBid()
        bid = Bid(str(uuid.uuid4()), price, energy, seller)
        with self.bid_lock:
            self.bids[bid.id] = bid
            log.info("[BID][NEW] %s", bid)
        return bid

    def delete_bid(self, bid_or_id: Union[str, Bid]):
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(bid_or_id, Bid):
            bid_or_id = bid_or_id.id
        with self.bid_lock:
            bid = self.bids.pop(bid_or_id, None)
            if not bid:
                raise BidNotFoundException()
            log.info("[BID][DEL] %s", bid)

    def accept_bid(self, bid_or_id: Union[str, Bid], buyer: str) -> Trade:
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(bid_or_id, Bid):
            bid_or_id = bid_or_id.id
        with self.bid_lock, self.trade_lock:
            bid = self.bids.pop(bid_or_id, None)
            if bid is None:
                raise BidNotFoundException()
            trade = Trade(bid, bid.seller, buyer)
            self.trades.append(trade)
            log.info("[TRADE] %s", trade)
            self.accounting[bid.seller] -= bid.energy
            self.accounting[buyer] += bid.energy
            self.ious[buyer][bid.seller] += bid.price
        return trade

    def __repr__(self):  # pragma: no cover
        return "<Market bids: {}, trades: {}, energy: {}, price: {}>".format(
            len(self.bids),
            len(self.trades),
            sum(t.bid.energy for t in self.trades),
            sum(t.bid.price for t in self.trades)
        )

    def display(self):  # pragma: no cover
        if self.trades:
            print("Trades:")
            trade_table = [['From', 'To', 'kWh', 'Price']] + [
                [trade.seller, trade.buyer, trade.bid.energy, trade.bid.price]
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
