import string
from collections import defaultdict

import pytest
from pendulum import DateTime

from d3a.models.events import MarketEvent
from hypothesis import strategies as st
from hypothesis.control import assume
from hypothesis.stateful import Bundle, RuleBasedStateMachine, precondition, rule

from d3a.exceptions import InvalidOffer, MarketReadOnlyException, OfferNotFoundException, \
    InvalidTrade, InvalidBid, BidNotFound
from d3a.models.market import Market


@pytest.yield_fixture
def market():
    return Market()


def test_market_offer(market: Market):
    offer = market.offer(10, 20, 'someone')

    assert market.offers[offer.id] == offer
    assert offer.energy == 20
    assert offer.price == 10
    assert offer.seller == 'someone'
    assert len(offer.id) == 36


def test_market_bid(market: Market):
    bid = market.bid(1, 2, 'bidder', 'seller')
    assert market.bids[bid.id] == bid
    assert bid.price == 1
    assert bid.energy == 2
    assert bid.buyer == 'bidder'
    assert bid.seller == 'seller'
    assert len(bid.id) == 36
    assert bid.market == market


def test_market_offer_invalid(market: Market):
    with pytest.raises(InvalidOffer):
        market.offer(10, -1, 'someone')


def test_market_bid_invalid(market: Market):
    with pytest.raises(InvalidBid):
        market.bid(10, -1, 'someone', 'noone')


def test_market_offer_readonly(market: Market):
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        market.offer(10, 10, 'A')


def test_market_offer_delete(market: Market):
    offer = market.offer(20, 10, 'someone')
    market.delete_offer(offer)

    assert offer.id not in market.offers


def test_market_offer_delete_id(market: Market):
    offer = market.offer(20, 10, 'someone')
    market.delete_offer(offer.id)

    assert offer.id not in market.offers


def test_market_offer_delete_missing(market: Market):
    with pytest.raises(OfferNotFoundException):
        market.delete_offer("no such offer")


def test_market_offer_delete_readonly(market: Market):
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        market.delete_offer("no such offer")


def test_market_bid_delete(market: Market):
    bid = market.bid(20, 10, 'someone', 'noone')
    assert bid.id in market.bids

    market.delete_bid(bid)
    assert bid.id not in market.bids


def test_market_bid_delete_id(market: Market):
    bid = market.bid(20, 10, 'someone', 'noone')
    assert bid.id in market.bids

    market.delete_bid(bid.id)
    assert bid.id not in market.bids


def test_market_bid_delete_missing(market: Market):
    with pytest.raises(BidNotFound):
        market.delete_bid("no such offer")


def test_market_trade(market: Market):
    offer = market.offer(20, 10, 'A')

    now = DateTime.now()
    trade = market.accept_offer(offer, 'B', time=now)
    assert trade
    assert trade == market.trades[0]
    assert trade.id
    assert trade.time == now
    assert trade.offer is offer
    assert trade.seller == 'A'
    assert trade.buyer == 'B'


def test_market_bid_trade(market: Market):
    bid = market.bid(20, 10, 'A', 'B')

    trade = market.accept_bid(bid, energy=10, seller='B')
    assert trade
    assert trade == market.trades[0]
    assert trade.id
    assert trade.offer is bid
    assert trade.seller == 'B'
    assert trade.buyer == 'A'


def test_market_trade_by_id(market: Market):
    offer = market.offer(20, 10, 'A')

    trade = market.accept_offer(offer.id, 'B')
    assert trade


def test_market_trade_readonly(market: Market):
    offer = market.offer(20, 10, 'A')
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        market.accept_offer(offer, 'B')


def test_market_trade_not_found(market: Market):
    offer = market.offer(20, 10, 'A')

    assert market.accept_offer(offer, 'B')
    with pytest.raises(OfferNotFoundException):
        market.accept_offer(offer, 'B')


def test_market_trade_bid_not_found(market: Market):
    bid = market.bid(20, 10, 'A', 'B')

    assert market.accept_bid(bid, 10, 'B')

    with pytest.raises(BidNotFound):
        market.accept_bid(bid, 10, 'B')


def test_market_trade_partial(market: Market):
    offer = market.offer(20, 20, 'A')

    trade = market.accept_offer(offer, 'B', energy=5)
    assert trade
    assert trade == market.trades[0]
    assert trade.id
    assert trade.offer is not offer
    assert trade.offer.energy == 5
    assert trade.offer.price == 5
    assert trade.offer.seller == 'A'
    assert trade.seller == 'A'
    assert trade.buyer == 'B'
    assert len(market.offers) == 1
    new_offer = list(market.offers.values())[0]
    assert new_offer is not offer
    assert new_offer.energy == 15
    assert new_offer.price == 15
    assert new_offer.seller == 'A'
    assert new_offer.id != offer.id


def test_market_trade_bid_partial(market: Market):
    bid = market.bid(20, 20, 'A', 'B')

    trade = market.accept_bid(bid, energy=5, seller='B')
    assert trade
    assert trade == market.trades[0]
    assert trade.id
    assert trade.offer is not bid
    assert trade.offer.energy == 5
    assert trade.offer.price == 5
    assert trade.offer.seller == 'B'
    assert trade.seller == 'B'
    assert trade.buyer == 'A'
    assert len(market.bids) == 0


@pytest.mark.parametrize('market_method', ('_update_accumulated_trade_price_energy',
                                           '_update_min_max_avg_trade_price'))
def test_market_accept_bid_respects_track_bid_by_not_updating_trade_stats(
        market: Market, called, market_method):
    setattr(market, market_method, called)

    bid = market.bid(20, 20, 'A', 'B')
    trade = market.accept_bid(bid, energy=5, seller='B', track_bid=False)
    assert trade
    assert len(getattr(market, market_method).calls) == 0


@pytest.mark.parametrize('energy', (0, 21))
def test_market_trade_partial_invalid(market: Market, energy):
    offer = market.offer(20, 20, 'A')

    with pytest.raises(InvalidTrade):
        market.accept_offer(offer, 'B', energy=energy)


@pytest.mark.parametrize('energy', (0, 21, 100, -20))
def test_market_trade_partial_bid_invalid(market: Market, energy):
    bid = market.bid(20, 20, 'A', 'B')

    with pytest.raises(InvalidTrade):
        market.accept_bid(bid, energy=energy, seller='A')


def test_market_acct_simple(market: Market):
    offer = market.offer(20, 10, 'A')
    market.accept_offer(offer, 'B')

    assert market.traded_energy['A'] == offer.energy
    assert market.traded_energy['B'] == -offer.energy
    assert market.bought_energy('A') == 0
    assert market.bought_energy('B') == offer.energy
    assert market.sold_energy('A') == offer.energy
    assert market.sold_energy('B') == 0


def test_market_acct_multiple(market: Market):
    offer1 = market.offer(10, 20, 'A')
    offer2 = market.offer(10, 10, 'A')
    market.accept_offer(offer1, 'B')
    market.accept_offer(offer2, 'C')

    assert market.traded_energy['A'] == offer1.energy + offer2.energy == 30
    assert market.traded_energy['B'] == -offer1.energy == -20
    assert market.traded_energy['C'] == -offer2.energy == -10
    assert market.bought_energy('A') == 0
    assert market.sold_energy('A') == offer1.energy + offer2.energy == 30
    assert market.bought_energy('B') == offer1.energy == 20
    assert market.bought_energy('C') == offer2.energy == 10


def test_market_avg_offer_price(market: Market):
    market.offer(1, 1, 'A')
    market.offer(3, 1, 'A')

    assert market.avg_offer_price == 2


def test_market_avg_offer_price_empty(market: Market):
    assert market.avg_offer_price == 0


def test_market_sorted_offers(market: Market):
    market.offer(5, 1, 'A')
    market.offer(3, 1, 'A')
    market.offer(1, 1, 'A')
    market.offer(2, 1, 'A')
    market.offer(4, 1, 'A')

    assert [o.price for o in market.sorted_offers] == [1, 2, 3, 4, 5]


def test_market_most_affordable_offers(market: Market):
    market.offer(5, 1, 'A')
    market.offer(3, 1, 'A')
    market.offer(1, 1, 'A')
    market.offer(10, 10, 'A')
    market.offer(20, 20, 'A')
    market.offer(20000, 20000, 'A')
    market.offer(2, 1, 'A')
    market.offer(4, 1, 'A')

    assert {o.price for o in market.most_affordable_offers} == {1, 10, 20, 20000}


def test_market_listeners_init(called):
    market = Market(notification_listener=called)
    market.offer(10, 20, 'A')

    assert len(called.calls) == 1


def test_market_listners_add(market, called):
    market.add_listener(called)
    market.offer(10, 20, 'A')

    assert len(called.calls) == 1


def test_market_listners_offer(market, called):
    market.add_listener(called)
    offer = market.offer(10, 20, 'A')

    assert len(called.calls) == 1
    assert called.calls[0][0] == (repr(MarketEvent.OFFER), )
    assert called.calls[0][1] == {'offer': repr(offer), 'market': repr(market)}


def test_market_listners_offer_changed(market, called):
    market.add_listener(called)
    offer = market.offer(10, 20, 'A')
    market.accept_offer(offer, 'B', energy=3)

    assert len(called.calls) == 3
    assert called.calls[1][0] == (repr(MarketEvent.OFFER_CHANGED), )
    call_kwargs = called.calls[1][1]
    call_kwargs.pop('market', None)
    assert call_kwargs == {
        'existing_offer': repr(offer),
        'new_offer': repr(list(market.offers.values())[0])
    }


def test_market_listners_offer_deleted(market, called):
    market.add_listener(called)
    offer = market.offer(10, 20, 'A')
    market.delete_offer(offer)

    assert len(called.calls) == 2
    assert called.calls[1][0] == (repr(MarketEvent.OFFER_DELETED), )
    assert called.calls[1][1] == {'offer': repr(offer), 'market': repr(market)}


@pytest.mark.parametrize(
    ('last_offer_size', 'traded_energy'),
    (
        (20, 10),
        (30, 0),
        (40, -10)
    )
)
def test_market_issuance_acct_reverse(market: Market, last_offer_size, traded_energy):
    offer1 = market.offer(10, 20, 'A')
    offer2 = market.offer(10, 10, 'A')
    offer3 = market.offer(10, last_offer_size, 'D')

    market.accept_offer(offer1, 'B')
    market.accept_offer(offer2, 'C')
    market.accept_offer(offer3, 'A')

    assert market.traded_energy['A'] == traded_energy


def test_market_iou(market: Market):
    offer = market.offer(10, 20, 'A')
    market.accept_offer(offer, 'B')

    assert market.ious['B']['A'] == 10


def test_market_accept_offer_yields_partial_trade(market: Market):
    offer = market.offer(2.0, 4, 'seller')
    trade = market.accept_offer(offer, 'buyer', energy=1)
    assert trade.offer.id == offer.id and trade.offer.energy == 1 and trade.residual.energy == 3


def test_market_accept_bid_yields_partial_bid_trade(market: Market):
    bid = market.bid(2.0, 4, 'buyer', 'seller')
    trade = market.accept_bid(bid, energy=1, seller='seller')
    assert trade.offer.id == bid.id and trade.offer.energy == 1


class MarketStateMachine(RuleBasedStateMachine):
    offers = Bundle('Offers')
    actors = Bundle('Actors')

    def __init__(self):
        super().__init__()
        self.market = Market()

    @rule(target=actors, actor=st.text(min_size=1, max_size=3,
                                       alphabet=string.ascii_letters + string.digits))
    def new_actor(self, actor):
        return actor

    @rule(target=offers, seller=actors, energy=st.integers(min_value=1), price=st.integers())
    def offer(self, seller, energy, price):
        return self.market.offer(price, energy, seller)

    @rule(offer=offers, buyer=actors)
    def trade(self, offer, buyer):
        assume(offer.id in self.market.offers)
        self.market.accept_offer(offer, buyer)

    @precondition(lambda self: self.market.offers)
    @rule()
    def check_avg_offer_price(self):
        price = sum(o.price for o in self.market.offers.values())
        energy = sum(o.energy for o in self.market.offers.values())
        assert self.market.avg_offer_price == round(price / energy, 4)

    @precondition(lambda self: self.market.trades)
    @rule()
    def check_avg_trade_price(self):
        price = sum(t.offer.price for t in self.market.trades)
        energy = sum(t.offer.energy for t in self.market.trades)
        assert self.market.avg_trade_price == round(price / energy, 4)

    @precondition(lambda self: self.market.traded_energy)
    @rule()
    def check_acct(self):
        actor_sums = defaultdict(int)
        for t in self.market.trades:
            actor_sums[t.seller] += t.offer.energy
            actor_sums[t.buyer] -= t.offer.energy
        for actor, sum_ in actor_sums.items():
            assert self.market.traded_energy[actor] == sum_
        assert sum(self.market.traded_energy.values()) == 0

    @precondition(lambda self: self.market.traded_energy)
    @rule()
    def check_iou_balance(self):
        seller_ious = defaultdict(int)
        buyer_ious = defaultdict(int)
        for t in self.market.trades:
            seller_ious[t.seller] += t.offer.price
            buyer_ious[t.buyer] += t.offer.price
        trade_sum = sum(t.offer.price for t in self.market.trades)

        for seller, iou in seller_ious.items():
            assert iou == sum(ious[seller] for ious in self.market.ious.values())

        for buyer, iou in buyer_ious.items():
            assert iou == sum(self.market.ious[buyer].values())

        assert trade_sum == sum(sum(i.values()) for i in self.market.ious.values())


TestMarketIOU = MarketStateMachine.TestCase
