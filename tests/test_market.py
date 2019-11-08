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
import string
from math import isclose

import pytest
from pendulum import DateTime

from d3a.constants import TIME_ZONE
from d3a.events.event_structures import MarketEvent

from hypothesis import strategies as st
from hypothesis.control import assume
from hypothesis.stateful import Bundle, RuleBasedStateMachine, precondition, rule

from d3a.d3a_core.exceptions import InvalidOffer, MarketReadOnlyException, \
    OfferNotFoundException, InvalidTrade, InvalidBalancingTradeException, InvalidBid, \
    BidNotFound, DeviceNotInRegistryError
from d3a.models.market.two_sided_pay_as_bid import TwoSidedPayAsBid
from d3a.models.market.two_sided_pay_as_clear import TwoSidedPayAsClear
from d3a.models.market.one_sided import OneSidedMarket
from d3a.models.market.market_structures import Bid, Offer, Trade
from d3a.models.market.balancing import BalancingMarket
from d3a_interface.constants_limits import ConstSettings
from d3a.d3a_core.util import add_or_create_key, subtract_or_create_key
from d3a.models.market import TransferFees

from d3a.d3a_core.device_registry import DeviceRegistry
device_registry_dict = {
    "A": {"balancing rates": (33, 35)},
    "someone": {"balancing rates": (33, 35)},
    "seller": {"balancing rates": (33, 35)},
}

transfer_fees = TransferFees(transfer_fee_pct=0, transfer_fee_const=0)


class FakeTwoSidedPayAsBid(TwoSidedPayAsBid):
    def __init__(self, bids=[], m_id=123, time_slot=DateTime.now()):
        super().__init__(transfer_fees=transfer_fees, time_slot=time_slot)
        self.id = m_id
        self._bids = bids
        self.offer_count = 0
        self.bid_count = 0
        self.forwarded_offer_id = 'fwd'
        self.forwarded_bid_id = 'fwd_bid_id'
        self.calls_energy = []
        self.calls_energy_bids = []
        self.calls_offers = []
        self.calls_bids = []
        self.calls_bids_price = []
        self.mcp_update_point = 20
        self.current_tick = 19
        # self.transfer_fee_ratio = transfer_fees.transfer_fee_pct / 100
        # self.transfer_fee_const = transfer_fees.transfer_fee_const

    def accept_offer(self, offer_or_id, buyer, *, energy=None, time=None, already_tracked=False,
                     trade_rate: float = None, trade_bid_info=None, buyer_origin=None):

        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        offer = self.offers.pop(offer_or_id, None)
        if offer is None:
            assert False

        self.calls_energy.append(energy)
        self.calls_offers.append(offer)

        if energy < offer.energy:
            residual_energy = offer.energy - energy
            residual = Offer('res', offer.price, residual_energy, offer.seller)
            traded = Offer(offer.id, offer.price, energy, offer.seller)
            return Trade('trade_id', time, traded, traded.seller, buyer, residual)
        else:
            return Trade('trade_id', time, offer, offer.seller, buyer)

    def accept_bid(self, bid: Bid, energy: float = None,
                   seller: str = None, buyer: str = None, already_tracked: bool = False,
                   trade_rate: float = None, trade_offer_info=None, time=None,
                   seller_origin=None):
        self.calls_energy_bids.append(energy)
        self.calls_bids.append(bid)
        self.calls_bids_price.append(bid.price)
        if trade_rate is None:
            trade_rate = bid.price / bid.energy
        else:
            assert trade_rate <= (bid.price / bid.energy)

        market_bid = [b for b in self.bids.values() if b.id == bid.id][0]
        if energy < market_bid.energy:
            residual_energy = bid.energy - energy
            residual = Bid('res', bid.price, residual_energy, bid.buyer, seller)
            traded = Bid(bid.id, (trade_rate * energy), energy, bid.buyer, seller)
            return Trade('trade_id', time, traded, traded.seller, bid.buyer, residual)
        else:
            traded = Bid(bid.id, (trade_rate * energy), energy, bid.buyer, seller)
            return Trade('trade_id', time, traded, traded.seller, bid.buyer)


def teardown_function():
    ConstSettings.IAASettings.MARKET_TYPE = 1


@pytest.yield_fixture
def market():
    return TwoSidedPayAsBid()


def test_double_sided_performs_pay_as_bid_matching(market):
    market.offers = {"offer1": Offer('id', 2, 2, 'other', 2)}

    market.bids = {"bid1": Bid('bid_id', 9, 10, 'B', 'S')}
    matched = list(market._perform_pay_as_bid_matching())
    assert len(matched) == 0
    market.bids = {"bid1": Bid('bid_id', 10, 10, 'B', 'S')}
    matched = list(market._perform_pay_as_bid_matching())
    assert len(matched) == 1

    bid, offer = matched[0]
    assert bid == list(market.bids.values())[0]
    assert offer == list(market.offers.values())[0]

    market.bids = {"bid1": Bid('bid_id1', 11, 10, 'B', 'S'),
                   "bid2": Bid('bid_id2', 9, 10, 'B', 'S'),
                   "bid3": Bid('bid_id3', 12, 10, 'B', 'S')}
    matched = list(market._perform_pay_as_bid_matching())
    assert len(matched) == 1
    bid, offer = matched[0]
    assert bid.id == 'bid_id3'
    assert bid.price == 12
    assert bid.energy == 10
    assert offer == list(market.offers.values())[0]


def test_device_registry(market=BalancingMarket()):
    with pytest.raises(DeviceNotInRegistryError):
        market.balancing_offer(10, 10, 'noone')


@pytest.mark.parametrize("market, offer", [
    (OneSidedMarket(time_slot=DateTime.now()), "offer"),
    (BalancingMarket(time_slot=DateTime.now()), "balancing_offer")
])
def test_market_offer(market, offer):
    DeviceRegistry.REGISTRY = device_registry_dict
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
    e_offer = getattr(market, offer)(10, 20, 'someone')
    assert market.offers[e_offer.id] == e_offer
    assert e_offer.energy == 20
    assert e_offer.price == 10
    assert e_offer.seller == 'someone'
    assert len(e_offer.id) == 36


def test_market_bid(market: TwoSidedPayAsBid):
    bid = market.bid(1, 2, 'bidder', 'seller')
    assert market.bids[bid.id] == bid
    assert bid.price == 1
    assert bid.energy == 2
    assert bid.buyer == 'bidder'
    assert bid.seller == 'seller'
    assert len(bid.id) == 36


def test_market_bid_accepts_bid_id(market: TwoSidedPayAsBid):
    bid = market.bid(1, 2, 'bidder', 'seller', bid_id='123')
    assert market.bids['123'] == bid
    assert bid.id == '123'
    assert bid.price == 1
    assert bid.energy == 2
    assert bid.buyer == 'bidder'
    assert bid.seller == 'seller'

    # Update existing bid is tested here
    bid = market.bid(3, 4, 'updated_bidder', 'updated_seller', bid_id='123')
    assert market.bids['123'] == bid
    assert bid.id == '123'
    assert isclose(bid.price, 3)
    assert bid.energy == 4
    assert bid.buyer == 'updated_bidder'
    assert bid.seller == 'updated_seller'


def test_market_offer_invalid(market: OneSidedMarket):
    with pytest.raises(InvalidOffer):
        market.offer(10, -1, 'someone')


def test_market_bid_invalid(market: TwoSidedPayAsBid):
    with pytest.raises(InvalidBid):
        market.bid(10, -1, 'someone', 'noone')


@pytest.mark.parametrize("market, offer", [
    (TwoSidedPayAsBid(), "offer"),
    (BalancingMarket(), "balancing_offer")
])
def test_market_offer_readonly(market, offer):
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        getattr(market, offer)(10, 10, 'A')


@pytest.mark.parametrize("market, offer", [
    (TwoSidedPayAsBid(time_slot=DateTime.now()), "offer"),
    (BalancingMarket(time_slot=DateTime.now()), "balancing_offer")
])
def test_market_offer_delete(market, offer):
    offer = getattr(market, offer)(20, 10, 'someone')
    market.delete_offer(offer)

    assert offer.id not in market.offers


@pytest.mark.parametrize("market",
                         [OneSidedMarket(),
                          BalancingMarket()])
def test_market_offer_delete_missing(market):
    with pytest.raises(OfferNotFoundException):
        market.delete_offer("no such offer")


@pytest.mark.parametrize("market",
                         [OneSidedMarket(),
                          BalancingMarket()])
def test_market_offer_delete_readonly(market):
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        market.delete_offer("no such offer")


def test_market_bid_delete(market: TwoSidedPayAsBid):
    bid = market.bid(20, 10, 'someone', 'noone')
    assert bid.id in market.bids

    market.delete_bid(bid)
    assert bid.id not in market.bids


def test_market_bid_delete_id(market: TwoSidedPayAsBid):
    bid = market.bid(20, 10, 'someone', 'noone')
    assert bid.id in market.bids

    market.delete_bid(bid.id)
    assert bid.id not in market.bids


def test_market_bid_delete_missing(market: TwoSidedPayAsBid):
    with pytest.raises(BidNotFound):
        market.delete_bid("no such offer")


@pytest.mark.parametrize("market, offer, accept_offer", [
    (OneSidedMarket(time_slot=DateTime.now()),
     "offer", "accept_offer"),
    (BalancingMarket(time_slot=DateTime.now()),
     "balancing_offer", "accept_offer")
])
def test_market_trade(market, offer, accept_offer):
    e_offer = getattr(market, offer)(20, 10, 'A')
    now = DateTime.now(tz=TIME_ZONE)
    trade = getattr(market, accept_offer)(offer_or_id=e_offer, buyer='B',
                                          energy=10, time=now)
    assert trade
    assert trade == market.trades[0]
    assert trade.id
    assert trade.time == now
    assert trade.offer == e_offer
    assert trade.seller == 'A'
    assert trade.buyer == 'B'


def test_balancing_market_negative_offer_trade(market=BalancingMarket(time_slot=DateTime.now())):  # NOQA
    offer = market.balancing_offer(20, -10, 'A')

    now = DateTime.now(tz=TIME_ZONE)
    trade = market.accept_offer(offer, 'B', time=now, energy=-10)
    assert trade
    assert trade == market.trades[0]
    assert trade.id
    assert trade.time == now
    assert trade.offer is offer
    assert trade.seller == 'A'
    assert trade.buyer == 'B'


def test_market_bid_trade(market=TwoSidedPayAsBid(time_slot=DateTime.now())):
    # market = TwoSidedPayAsBid(time_slot=DateTime.now())
    bid = market.bid(20, 10, 'A', 'B', original_bid_price=20)

    trade = market.accept_bid(bid, energy=10, seller='B', trade_offer_info=[2, 2, 0.5, 0.5, 2])
    assert trade
    assert trade.id == market.trades[0].id
    assert trade.id
    assert trade.offer.price == bid.price
    assert trade.offer.energy == bid.energy
    assert trade.seller == 'B'
    assert trade.buyer == 'A'
    assert not trade.residual


@pytest.mark.parametrize("market, offer, accept_offer", [
    (OneSidedMarket(time_slot=DateTime.now()),
     "offer", "accept_offer"),
    (BalancingMarket(time_slot=DateTime.now()),
     "balancing_offer", "accept_offer")
])
def test_market_trade_by_id(market, offer, accept_offer):
    e_offer = getattr(market, offer)(20, 10, 'A')
    now = DateTime.now(tz=TIME_ZONE)
    trade = getattr(market, accept_offer)(offer_or_id=e_offer.id, buyer='B',
                                          energy=10, time=now)
    assert trade


@pytest.mark.parametrize("market, offer, accept_offer", [
    (OneSidedMarket(),
     "offer", "accept_offer"),
    (BalancingMarket(),
     "balancing_offer", "accept_offer")
])
def test_market_trade_readonly(market, offer, accept_offer):
    e_offer = getattr(market, offer)(20, 10, 'A')
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        getattr(market, accept_offer)(e_offer, 'B')


@pytest.mark.parametrize("market, offer, accept_offer", [
    (OneSidedMarket(time_slot=DateTime.now()),
     "offer", "accept_offer"),
    (BalancingMarket(time_slot=DateTime.now()),
     "balancing_offer", "accept_offer")
])
def test_market_trade_not_found(market, offer, accept_offer):
    e_offer = getattr(market, offer)(20, 10, 'A')

    assert getattr(market, accept_offer)(offer_or_id=e_offer, buyer='B', energy=10)
    with pytest.raises(OfferNotFoundException):
        getattr(market, accept_offer)(offer_or_id=e_offer, buyer='B', energy=10)


def test_market_trade_bid_not_found(market=TwoSidedPayAsBid(time_slot=DateTime.now())):
    bid = market.bid(20, 10, 'A', 'B')

    assert market.accept_bid(bid, 10, 'B', trade_offer_info=[2, 2, 1, 1, 2])

    with pytest.raises(BidNotFound):
        market.accept_bid(bid, 10, 'B', trade_offer_info=[2, 2, 1, 1, 2])


@pytest.mark.parametrize("market, offer, accept_offer", [
    (OneSidedMarket(time_slot=DateTime.now()),
     "offer", "accept_offer"),
    (BalancingMarket(time_slot=DateTime.now()),
     "balancing_offer", "accept_offer")
])
def test_market_trade_partial(market, offer, accept_offer):
    e_offer = getattr(market, offer)(20, 20, 'A')

    trade = getattr(market, accept_offer)(offer_or_id=e_offer, buyer='B', energy=5)
    assert trade
    assert trade == market.trades[0]
    assert trade.id
    assert trade.offer is not e_offer
    assert trade.offer.energy == 5
    assert trade.offer.price == 5
    assert trade.offer.seller == 'A'
    assert trade.seller == 'A'
    assert trade.buyer == 'B'
    assert len(market.offers) == 1
    new_offer = list(market.offers.values())[0]
    assert new_offer is not e_offer
    assert new_offer.energy == 15
    assert new_offer.price == 15
    assert new_offer.seller == 'A'
    assert new_offer.id != e_offer.id


def test_market_trade_bid_partial(market=TwoSidedPayAsBid(time_slot=DateTime.now())):
    bid = market.bid(20, 20, 'A', 'B', original_bid_price=20)

    trade = market.accept_bid(bid, energy=5, seller='B', trade_offer_info=[1, 1, 1, 1, 1])
    assert trade
    assert trade.id == market.trades[0].id
    assert trade.id
    assert trade.offer is not bid
    assert trade.offer.energy == 5
    assert trade.offer.price == 5
    assert trade.offer.seller == 'B'
    assert trade.seller == 'B'
    assert trade.buyer == 'A'
    assert trade.residual
    assert len(market.bids) == 1
    assert trade.residual.id in market.bids
    assert market.bids[trade.residual.id].energy == 15
    assert isclose(market.bids[trade.residual.id].price, 15)
    assert market.bids[trade.residual.id].seller == 'B'
    assert market.bids[trade.residual.id].buyer == 'A'


def test_market_accept_bid_emits_bid_traded_and_bid_deleted_event(
        called, market=TwoSidedPayAsBid(time_slot=DateTime.now())):
    market.add_listener(called)
    bid = market.bid(20, 20, 'A', 'B')
    trade = market.accept_bid(bid, trade_offer_info=[1, 1, 1, 1, 1])
    assert len(called.calls) == 2
    assert called.calls[0][0] == (repr(MarketEvent.BID_TRADED), )
    assert called.calls[1][0] == (repr(MarketEvent.BID_DELETED), )
    assert called.calls[0][1] == {
        'market_id': repr(market.id),
        'bid_trade': repr(trade),
    }
    assert called.calls[1][1] == {
        'market_id': repr(market.id),
        'bid': repr(bid),
    }


def test_market_accept_bid_does_not_emit_bid_deleted_on_partial_bid(
        called, market=TwoSidedPayAsBid(time_slot=DateTime.now())):
    market.add_listener(called)
    bid = market.bid(20, 20, 'A', 'B')
    trade = market.accept_bid(bid, energy=1, trade_offer_info=[1, 1, 1, 1, 1])
    assert all([ev != repr(MarketEvent.BID_DELETED) for c in called.calls for ev in c[0]])
    assert len(called.calls) == 2
    assert called.calls[0][0] == (repr(MarketEvent.BID_CHANGED),)
    assert called.calls[1][0] == (repr(MarketEvent.BID_TRADED),)
    assert called.calls[1][1] == {
        'market_id': repr(market.id),
        'bid_trade': repr(trade),
    }


@pytest.mark.parametrize('market_method', ('_update_accumulated_trade_price_energy',
                                           '_update_min_max_avg_trade_prices'))
def test_market_accept_bid_always_updates_trade_stats(
        called, market_method, market=TwoSidedPayAsBid(time_slot=DateTime.now())):
    setattr(market, market_method, called)

    bid = market.bid(20, 20, 'A', 'B')
    trade = market.accept_bid(bid, energy=5, seller='B', trade_offer_info=[1, 1, 1, 1, 1])
    assert trade
    assert len(getattr(market, market_method).calls) == 1


@pytest.mark.parametrize("market, offer, accept_offer, energy, exception", [
    (OneSidedMarket(time_slot=DateTime.now()),
     "offer", "accept_offer", 0, InvalidTrade),
    (OneSidedMarket(time_slot=DateTime.now()),
     "offer", "accept_offer", 21, InvalidTrade),
    (BalancingMarket(time_slot=DateTime.now()), "balancing_offer",
     "accept_offer", 0, InvalidBalancingTradeException),
    (BalancingMarket(time_slot=DateTime.now()), "balancing_offer",
     "accept_offer", 21, InvalidBalancingTradeException)
])
def test_market_trade_partial_invalid(market, offer, accept_offer, energy, exception):
    e_offer = getattr(market, offer)(20, 20, 'A')
    with pytest.raises(exception):
        getattr(market, accept_offer)(offer_or_id=e_offer, buyer='B', energy=energy)


@pytest.mark.parametrize('energy', (0, 21, 100, -20))
def test_market_trade_partial_bid_invalid(
        energy, market=TwoSidedPayAsBid(time_slot=DateTime.now())):
    bid = market.bid(20, 20, 'A', 'B')

    with pytest.raises(InvalidTrade):
        market.accept_bid(bid, energy=energy, seller='A', trade_offer_info=[1, 1, 1, 1, 1])


def test_market_acct_simple(market=OneSidedMarket(time_slot=DateTime.now())):
    offer = market.offer(20, 10, 'A')
    market.accept_offer(offer, 'B')

    assert market.traded_energy['A'] == offer.energy
    assert market.traded_energy['B'] == -offer.energy
    assert market.bought_energy('A') == 0
    assert market.bought_energy('B') == offer.energy
    assert market.sold_energy('A') == offer.energy
    assert market.sold_energy('B') == 0


def test_market_acct_multiple(market=OneSidedMarket(time_slot=DateTime.now())):
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


@pytest.mark.parametrize("market, offer", [
    (OneSidedMarket(time_slot=DateTime.now()), "offer"),
    (BalancingMarket(time_slot=DateTime.now()), "balancing_offer")
])
def test_market_avg_offer_price(market, offer):
    getattr(market, offer)(1, 1, 'A')
    getattr(market, offer)(3, 1, 'A')

    assert market.avg_offer_price == 2


@pytest.mark.parametrize("market",
                         [OneSidedMarket(time_slot=DateTime.now()),
                          BalancingMarket(time_slot=DateTime.now())])
def test_market_avg_offer_price_empty(market):
    assert market.avg_offer_price == 0


@pytest.mark.parametrize("market, offer", [
    (OneSidedMarket(time_slot=DateTime.now()), "offer"),
    (BalancingMarket(time_slot=DateTime.now()), "balancing_offer")
])
def test_market_sorted_offers(market, offer):
    getattr(market, offer)(5, 1, 'A')
    getattr(market, offer)(3, 1, 'A')
    getattr(market, offer)(1, 1, 'A')
    getattr(market, offer)(2, 1, 'A')
    getattr(market, offer)(4, 1, 'A')

    assert [o.price for o in market.sorted_offers] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("market, offer", [
    (OneSidedMarket(time_slot=DateTime.now()), "offer"),
    (BalancingMarket(time_slot=DateTime.now()), "balancing_offer")
])
def test_market_most_affordable_offers(market, offer):
    getattr(market, offer)(5, 1, 'A')
    getattr(market, offer)(3, 1, 'A')
    getattr(market, offer)(1, 1, 'A')
    getattr(market, offer)(10, 10, 'A')
    getattr(market, offer)(20, 20, 'A')
    getattr(market, offer)(20000, 20000, 'A')
    getattr(market, offer)(2, 1, 'A')
    getattr(market, offer)(4, 1, 'A')

    assert {o.price for o in market.most_affordable_offers} == {1, 10, 20, 20000}


@pytest.mark.parametrize("market, offer", [
    (OneSidedMarket, "offer"),
    (BalancingMarket, "balancing_offer")
])
def test_market_listeners_init(market, offer, called):
    markt = market(time_slot=DateTime.now(), notification_listener=called)
    getattr(markt, offer)(10, 20, 'A')
    assert len(called.calls) == 1


@pytest.mark.parametrize("market, offer, add_listener", [
    (OneSidedMarket(time_slot=DateTime.now()),
     "offer", "add_listener"),
    (BalancingMarket(time_slot=DateTime.now()),
     "balancing_offer", "add_listener")
])
def test_market_listeners_add(market, offer, add_listener, called):
    getattr(market, add_listener)(called)
    getattr(market, offer)(10, 20, 'A')

    assert len(called.calls) == 1


@pytest.mark.parametrize("market, offer, add_listener, event", [
    (OneSidedMarket(time_slot=DateTime.now()), "offer",
     "add_listener", MarketEvent.OFFER),
    (BalancingMarket(time_slot=DateTime.now()), "balancing_offer",
     "add_listener", MarketEvent.BALANCING_OFFER)
])
def test_market_listeners_offer(market, offer, add_listener, event, called):
    getattr(market, add_listener)(called)
    e_offer = getattr(market, offer)(10, 20, 'A')
    assert len(called.calls) == 1
    assert called.calls[0][0] == (repr(event), )
    assert called.calls[0][1] == {'offer': repr(e_offer), 'market_id': repr(market.id)}


@pytest.mark.parametrize("market, offer, accept_offer, add_listener, event", [
    (OneSidedMarket(time_slot=DateTime.now()), "offer", "accept_offer",
     "add_listener", MarketEvent.OFFER_CHANGED),
    (BalancingMarket(time_slot=DateTime.now()),
     "balancing_offer", "accept_offer",
     "add_listener", MarketEvent.BALANCING_OFFER_CHANGED)
])
def test_market_listeners_offer_changed(market, offer, accept_offer, add_listener, event, called):
    getattr(market, add_listener)(called)
    e_offer = getattr(market, offer)(10, 20, 'A')
    getattr(market, accept_offer)(e_offer, 'B', energy=3)
    assert len(called.calls) == 3
    assert called.calls[1][0] == (repr(event), )
    call_kwargs = called.calls[1][1]
    call_kwargs.pop('market_id', None)
    assert call_kwargs == {
        'existing_offer': repr(e_offer),
        'new_offer': repr(list(market.offers.values())[0])
    }


@pytest.mark.parametrize("market, offer, delete_offer, add_listener, event", [
    (OneSidedMarket(time_slot=DateTime.now()), "offer", "delete_offer",
     "add_listener", MarketEvent.OFFER_DELETED),
    (BalancingMarket(time_slot=DateTime.now()),
     "balancing_offer", "delete_balancing_offer",
     "add_listener", MarketEvent.BALANCING_OFFER_DELETED)
])
def test_market_listeners_offer_deleted(market, offer, delete_offer, add_listener, event, called):
    getattr(market, add_listener)(called)
    e_offer = getattr(market, offer)(10, 20, 'A')
    getattr(market, delete_offer)(e_offer)

    assert len(called.calls) == 2
    assert called.calls[1][0] == (repr(event), )
    assert called.calls[1][1] == {'offer': repr(e_offer), 'market_id': repr(market.id)}


@pytest.mark.parametrize(
    ('last_offer_size', 'traded_energy'),
    (
        (20, 10),
        (30, 0),
        (40, -10)
    )
)
def test_market_issuance_acct_reverse(last_offer_size, traded_energy):
    market = OneSidedMarket(time_slot=DateTime.now())
    offer1 = market.offer(10, 20, 'A')
    offer2 = market.offer(10, 10, 'A')
    offer3 = market.offer(10, last_offer_size, 'D')

    market.accept_offer(offer1, 'B')
    market.accept_offer(offer2, 'C')
    market.accept_offer(offer3, 'A')
    assert market.traded_energy['A'] == traded_energy


@pytest.mark.parametrize("market, offer, accept_offer", [
    (OneSidedMarket(time_slot=DateTime.now()),
     "offer", "accept_offer"),
    (BalancingMarket(time_slot=DateTime.now()),
     "balancing_offer", "accept_offer")
])
def test_market_accept_offer_yields_partial_trade(market, offer, accept_offer):
    e_offer = getattr(market, offer)(2.0, 4, 'seller')
    trade = getattr(market, accept_offer)(e_offer, 'buyer', energy=1)
    assert trade.offer.id == e_offer.id and trade.offer.energy == 1 and trade.residual.energy == 3


def test_market_accept_bid_yields_partial_bid_trade(
        market=TwoSidedPayAsBid(time_slot=DateTime.now())):
    bid = market.bid(2.0, 4, 'buyer', 'seller')
    trade = market.accept_bid(bid, energy=1, seller='seller', trade_offer_info=[2, 2, 1, 1, 2])
    assert trade.offer.id == bid.id and trade.offer.energy == 1


@pytest.yield_fixture
def pac_market():
    return TwoSidedPayAsClear(time_slot=DateTime.now())


@pytest.mark.parametrize("offer, bid, MCP", [
    ([1, 2, 3, 4, 5, 6, 7], [1, 2, 3, 4, 5, 6, 7], 4),
    ([1, 2, 3, 4, 5, 6, 7], [7, 6, 5, 4, 3, 2, 1], 4),
    ([8, 9, 10, 11, 12, 13, 14], [8, 9, 10, 11, 12, 13, 14], 11),
    ([2, 3, 3, 5, 6, 7, 8], [1, 2, 3, 4, 5, 6, 7], 5),
])
@pytest.mark.parametrize("algorithm", [1, 2])
def test_double_sided_market_performs_pay_as_clear_matching(pac_market,
                                                            offer, bid, MCP, algorithm):
    ConstSettings.IAASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM = algorithm
    pac_market.offers = {"offer1": Offer('id1', offer[0], 1, 'other'),
                         "offer2": Offer('id2', offer[1], 1, 'other'),
                         "offer3": Offer('id3', offer[2], 1, 'other'),
                         "offer4": Offer('id4', offer[3], 1, 'other'),
                         "offer5": Offer('id5', offer[4], 1, 'other'),
                         "offer6": Offer('id6', offer[5], 1, 'other'),
                         "offer7": Offer('id7', offer[6], 1, 'other')}

    pac_market.bids = {"bid1": Bid('bid_id1', bid[0], 1, 'B', 'S'),
                       "bid2": Bid('bid_id2', bid[1], 1, 'B', 'S'),
                       "bid3": Bid('bid_id3', bid[2], 1, 'B', 'S'),
                       "bid4": Bid('bid_id4', bid[3], 1, 'B', 'S'),
                       "bid5": Bid('bid_id5', bid[4], 1, 'B', 'S'),
                       "bid6": Bid('bid_id6', bid[5], 1, 'B', 'S'),
                       "bid7": Bid('bid_id7', bid[6], 1, 'B', 'S')}

    matched = pac_market._perform_pay_as_clear_matching()[0]
    assert matched == MCP


def test_double_sided_pay_as_clear_market_works_with_floats(pac_market):
    ConstSettings.IAASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM = 1
    pac_market.offers = {"offer1": Offer('id1', 1.1, 1, 'other'),
                         "offer2": Offer('id2', 2.2, 1, 'other'),
                         "offer3": Offer('id3', 3.3, 1, 'other')}

    pac_market.bids = {
                    "bid1": Bid('bid_id1', 3.3, 1, 'B', 'S'),
                    "bid2": Bid('bid_id2', 2.2, 1, 'B', 'S'),
                    "bid3": Bid('bid_id3', 1.1, 1, 'B', 'S')}

    matched = pac_market._perform_pay_as_clear_matching()[0]
    assert matched == 2.2


@pytest.yield_fixture
def pab_market():
    return FakeTwoSidedPayAsBid()


def test_double_sided_pay_as_bid_market_match_offer_bids(pab_market):
    pab_market.calls_offers = []
    pab_market.calls_bids = []
    offer = Offer('offer1', 2, 2, 'other', 2)
    pab_market.offers = {"offer1": offer}

    source_bid = Bid('bid_id3', 12, 10, 'B', 'S', original_bid_price=12)
    pab_market.bids = {"bid_id": Bid('bid_id', 10, 10, 'B', 'S'),
                       "bid_id1": Bid('bid_id1', 11, 10, 'B', 'S'),
                       "bid_id2": Bid('bid_id2', 9, 10, 'B', 'S'),
                       "bid_id3": source_bid}

    pab_market.match_offers_bids()
    assert len(pab_market.calls_offers) == 1
    offer = pab_market.calls_offers[0]
    assert offer.id == offer.id
    assert offer.energy == offer.energy
    assert offer.price == offer.price

    assert len(pab_market.calls_bids) == 1
    bid = pab_market.calls_bids[0]
    assert bid.id == source_bid.id
    assert bid.energy == source_bid.energy
    assert bid.price == source_bid.price


class MarketStateMachine(RuleBasedStateMachine):
    offers = Bundle('Offers')
    actors = Bundle('Actors')

    def __init__(self):
        self.market = OneSidedMarket(time_slot=DateTime.now())
        super().__init__()

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
        actor_sums = {}
        for t in self.market.trades:
            actor_sums = add_or_create_key(actor_sums, t.seller, t.offer.energy)
            actor_sums = subtract_or_create_key(actor_sums, t.buyer, t.offer.energy)
        for actor, sum_ in actor_sums.items():
            assert self.market.traded_energy[actor] == sum_
        assert sum(self.market.traded_energy.values()) == 0


TestMarketIOU = MarketStateMachine.TestCase
