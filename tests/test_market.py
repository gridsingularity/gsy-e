import random
import string
from collections import defaultdict

import pytest
from hypothesis import strategies as st
from hypothesis.control import assume
from hypothesis.stateful import RuleBasedStateMachine, Bundle, rule, precondition

from d3a.exceptions import MarketReadOnlyException, BidNotFoundException, InvalidBid
from d3a.models.market import Market


@pytest.yield_fixture
def market():
    return Market()


def test_market_bid(market: Market):
    bid = market.bid(20, 10, 'someone')

    assert market.bids[bid.id] == bid
    assert bid.energy == 20
    assert bid.price == 10
    assert bid.seller == 'someone'
    assert len(bid.id) == 36


def test_market_bid_invalid(market: Market):
    with pytest.raises(InvalidBid):
        market.bid(-1, 10, 'someone')


def test_market_bid_readonly(market: Market):
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        market.bid(10, 10, 'A')


def test_market_bid_delete(market: Market):
    bid = market.bid(20, 10, 'someone')
    market.delete_bid(bid)

    assert bid.id not in market.bids


def test_market_bid_delete_id(market: Market):
    bid = market.bid(20, 10, 'someone')
    market.delete_bid(bid.id)

    assert bid.id not in market.bids


def test_market_bid_delete_missing(market: Market):
    with pytest.raises(BidNotFoundException):
        market.delete_bid("no such bid")


def test_market_bid_delete_readonly(market: Market):
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        market.delete_bid("no such bid")


def test_market_trade(market: Market):
    bid = market.bid(20, 10, 'A')

    trade = market.accept_bid(bid, 'B')
    assert trade
    assert trade == market.trades[0]
    assert trade.bid is bid
    assert trade.seller == 'A'
    assert trade.buyer == 'B'


def test_market_trade_by_id(market: Market):
    bid = market.bid(20, 10, 'A')

    trade = market.accept_bid(bid.id, 'B')
    assert trade


def test_market_trade_readonly(market: Market):
    bid = market.bid(20, 10, 'A')
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        market.accept_bid(bid, 'B')


def test_market_trade_not_found(market: Market):
    bid = market.bid(20, 10, 'A')

    assert market.accept_bid(bid, 'B')
    with pytest.raises(BidNotFoundException):
        market.accept_bid(bid, 'B')


def test_market_acct_simple(market: Market):
    bid = market.bid(20, 10, 'A')
    market.accept_bid(bid, 'B')

    assert market.accounting['A'] == -bid.energy
    assert market.accounting['B'] == bid.energy


def test_market_acct_multiple(market: Market):
    bid1 = market.bid(20, 10, 'A')
    bid2 = market.bid(10, 10, 'A')
    market.accept_bid(bid1, 'B')
    market.accept_bid(bid2, 'C')

    assert market.accounting['A'] == -bid1.energy + -bid2.energy == -30
    assert market.accounting['B'] == bid1.energy == 20
    assert market.accounting['C'] == bid2.energy == 10


@pytest.mark.parametrize(
    ('last_bid_size', 'accounting'),
    (
        (20, -10),
        (30, 0),
        (40, 10)
    )
)
def test_market_issuance_acct_reverse(market: Market, last_bid_size, accounting):
    bid1 = market.bid(20, 10, 'A')
    bid2 = market.bid(10, 10, 'A')
    bid3 = market.bid(last_bid_size, 10, 'D')

    market.accept_bid(bid1, 'B')
    market.accept_bid(bid2, 'C')
    market.accept_bid(bid3, 'A')

    assert market.accounting['A'] == accounting


def test_market_iou(market: Market):
    bid = market.bid(20, 10, 'A')
    market.accept_bid(bid, 'B')

    assert market.ious['B']['A'] == 10


class MarketStateMachine(RuleBasedStateMachine):
    bids = Bundle('Bids')
    actors = Bundle('Actors')

    def __init__(self):
        super().__init__()
        self.market = Market()

    @rule(target=actors, actor=st.text(min_size=1, max_size=3, alphabet=string.ascii_letters + string.digits))
    def new_actor(self, actor):
        return actor

    @rule(target=bids, seller=actors, energy=st.integers(min_value=1), price=st.integers())
    def bid(self, seller, energy, price):
        return self.market.bid(energy, price, seller)

    @rule(bid=bids, buyer=actors)
    def trade(self, bid, buyer):
        assume(bid.id in self.market.bids)
        self.market.accept_bid(bid, buyer)

    @precondition(lambda self: self.market.accounting)
    @rule()
    def check_acct(self):
        actor_sums = defaultdict(int)
        for t in self.market.trades:
            actor_sums[t.seller] -= t.bid.energy
            actor_sums[t.buyer] += t.bid.energy
        for actor, sum_ in actor_sums.items():
            assert self.market.accounting[actor] == sum_
        assert sum(self.market.accounting.values()) == 0

    @precondition(lambda self: self.market.accounting)
    @rule()
    def check_iou_balance(self):
        seller_ious = defaultdict(int)
        buyer_ious = defaultdict(int)
        for t in self.market.trades:
            seller_ious[t.seller] += t.bid.price
            buyer_ious[t.buyer] += t.bid.price
        trade_sum = sum(t.bid.price for t in self.market.trades)

        for seller, iou in seller_ious.items():
            assert iou == sum(ious[seller] for ious in self.market.ious.values())

        for buyer, iou in buyer_ious.items():
            assert iou == sum(self.market.ious[buyer].values())

        assert trade_sum == sum(sum(i.values()) for i in self.market.ious.values())

TestMarketIOU = MarketStateMachine.TestCase
