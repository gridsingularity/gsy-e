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
from copy import deepcopy
import pytest
from pendulum import DateTime, now
from unittest.mock import MagicMock
from uuid import uuid4

from d3a.constants import TIME_ZONE
from d3a.events.event_structures import MarketEvent
from d3a.models.myco_matcher.pay_as_bid import PayAsBidMatcher

from hypothesis import strategies as st
from hypothesis.control import assume
from hypothesis.stateful import Bundle, RuleBasedStateMachine, precondition, rule

from d3a.d3a_core.exceptions import InvalidOffer, MarketReadOnlyException, \
    OfferNotFoundException, InvalidTrade, InvalidBalancingTradeException, InvalidBid, \
    BidNotFound, DeviceNotInRegistryError
from d3a.models.market.two_sided import TwoSidedMarket
from d3a.models.myco_matcher.pay_as_clear import PayAsClearMatcher
from d3a.models.market.one_sided import OneSidedMarket
from d3a.models.market.market_structures import Bid, Offer, Trade, TradeBidOfferInfo
from d3a.models.market.balancing import BalancingMarket
from d3a.models.market.blockchain_interface import NonBlockchainInterface
from d3a_interface.constants_limits import ConstSettings
from d3a.d3a_core.util import add_or_create_key, subtract_or_create_key
from d3a.models.market import GridFee

from d3a.d3a_core.device_registry import DeviceRegistry
device_registry_dict = {
    "A": {"balancing rates": (33, 35)},
    "someone": {"balancing rates": (33, 35)},
    "seller": {"balancing rates": (33, 35)},
}

transfer_fees = GridFee(grid_fee_percentage=0, grid_fee_const=0)


class FakeTwoSidedPayAsBid(TwoSidedMarket):
    def __init__(self, bids=[], m_id=123, time_slot=now()):
        super().__init__(bc=MagicMock(),
                         grid_fees=transfer_fees, time_slot=time_slot)
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
        # self.transfer_fee_ratio = transfer_fees.grid_fee_percentage / 100
        # self.grid_fee_const = transfer_fees.grid_fee_const

    def accept_offer(self, offer_or_id, buyer, *, energy=None, time=None, already_tracked=False,
                     trade_rate: float = None, trade_bid_info=None, buyer_origin=None,
                     buyer_origin_id=None, buyer_id=None):

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
                   seller_origin=None, seller_origin_id=None, seller_id=None):
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
            residual = Bid('res', bid.time, bid.price, residual_energy, bid.buyer, seller)
            traded = Bid(bid.id, bid.time, (trade_rate * energy), energy, bid.buyer, seller)
            return Trade('trade_id', time, traded, bid.buyer, residual)
        else:
            traded = Bid(bid.id, bid.time, (trade_rate * energy), energy, bid.buyer, seller)
            return Trade('trade_id', time, traded, bid.buyer)


def teardown_function():
    ConstSettings.IAASettings.MARKET_TYPE = 1


@pytest.yield_fixture
def market():
    return TwoSidedMarket(time_slot=now())


@pytest.yield_fixture
def market_matcher():
    return PayAsBidMatcher()


def test_double_sided_performs_pay_as_bid_matching(market, market_matcher):
    market.offers = {"offer1": Offer('id', now(), 2, 2, 'other', 2)}

    market.bids = {"bid1": Bid('bid_id', now(), 9, 10, 'B', 'S')}
    matched = list(market_matcher.calculate_match_recommendation(
        market.bids, market.offers))
    assert len(matched) == 0
    market.bids = {"bid1": Bid('bid_id', now(), 11, 10, 'B', 'S')}
    matched = list(market_matcher.calculate_match_recommendation(
        market.bids, market.offers))
    assert len(matched) == 1

    assert matched[0].bid == list(market.bids.values())[0]
    assert matched[0].offer == list(market.offers.values())[0]

    market.bids = {"bid1": Bid('bid_id1', now(), 11, 10, 'B', 'S'),
                   "bid2": Bid('bid_id2', now(), 9, 10, 'B', 'S'),
                   "bid3": Bid('bid_id3', now(), 12, 10, 'B', 'S')}
    matched = list(market_matcher.calculate_match_recommendation(
        market.bids, market.offers))
    assert len(matched) == 1
    assert matched[0].bid.id == 'bid_id3'
    assert matched[0].bid.price == 12
    assert matched[0].bid.energy == 10
    assert matched[0].offer == list(market.offers.values())[0]


def test_device_registry(market=BalancingMarket()):
    with pytest.raises(DeviceNotInRegistryError):
        market.balancing_offer(10, 10, 'noone')


@pytest.mark.parametrize("market, offer", [
    (OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "offer"),
    (BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "balancing_offer")
])
def test_market_offer(market, offer):
    DeviceRegistry.REGISTRY = device_registry_dict
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
    e_offer = getattr(market, offer)(10, 20, 'someone', 'someone')
    assert market.offers[e_offer.id] == e_offer
    assert e_offer.energy == 20
    assert e_offer.price == 10
    assert e_offer.seller == 'someone'
    assert len(e_offer.id) == 36


def test_market_bid(market: TwoSidedMarket):
    bid = market.bid(1, 2, 'bidder', 'bidder')
    assert market.bids[bid.id] == bid
    assert bid.price == 1
    assert bid.energy == 2
    assert bid.buyer == 'bidder'
    assert len(bid.id) == 36


def test_market_bid_accepts_bid_id(market: TwoSidedMarket):
    bid = market.bid(1, 2, 'bidder', 'bidder', bid_id='123')
    assert market.bids['123'] == bid
    assert bid.id == '123'
    assert bid.price == 1
    assert bid.energy == 2
    assert bid.buyer == 'bidder'

    # Update existing bid is tested here
    bid = market.bid(3, 4, 'updated_bidder', 'updated_bidder', bid_id='123')
    assert market.bids['123'] == bid
    assert bid.id == '123'
    assert isclose(bid.price, 3)
    assert bid.energy == 4
    assert bid.buyer == 'updated_bidder'


def test_market_offer_invalid(market: OneSidedMarket):
    with pytest.raises(InvalidOffer):
        market.offer(10, -1, 'someone', 'someone')


def test_market_bid_invalid(market: TwoSidedMarket):
    with pytest.raises(InvalidBid):
        market.bid(10, -1, 'someone',  'someone')


@pytest.mark.parametrize("market, offer", [
    (TwoSidedMarket(), "offer"),
    (BalancingMarket(), "balancing_offer")
])
def test_market_offer_readonly(market, offer):
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        getattr(market, offer)(10, 10, 'A', 'A')


@pytest.mark.parametrize("market, offer", [
    (TwoSidedMarket(bc=MagicMock(), time_slot=now()), "offer"),
    (BalancingMarket(bc=MagicMock(), time_slot=now()), "balancing_offer")
])
def test_market_offer_delete(market, offer):
    print(f"market: {market.bc_interface}")
    offer = getattr(market, offer)(20, 10, 'someone', 'someone')
    market.delete_offer(offer)

    assert offer.id not in market.offers


@pytest.mark.parametrize("market",
                         [OneSidedMarket(bc=MagicMock()),
                          BalancingMarket(bc=MagicMock())])
def test_market_offer_delete_missing(market):
    with pytest.raises(OfferNotFoundException):
        market.delete_offer("no such offer")


@pytest.mark.parametrize("market",
                         [OneSidedMarket(bc=MagicMock()),
                          BalancingMarket(bc=MagicMock())])
def test_market_offer_delete_readonly(market):
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        market.delete_offer("no such offer")


def test_market_bid_delete(market: TwoSidedMarket):
    bid = market.bid(20, 10, 'someone', 'someone')
    assert bid.id in market.bids

    market.delete_bid(bid)
    assert bid.id not in market.bids


def test_market_bid_delete_id(market: TwoSidedMarket):
    bid = market.bid(20, 10, 'someone', 'someone')
    assert bid.id in market.bids

    market.delete_bid(bid.id)
    assert bid.id not in market.bids


def test_market_bid_delete_missing(market: TwoSidedMarket):
    with pytest.raises(BidNotFound):
        market.delete_bid("no such offer")


@pytest.mark.parametrize("market, offer, accept_offer", [
    (OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
     "offer", "accept_offer"),
    (BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
     "balancing_offer", "accept_offer")
])
def test_market_trade(market, offer, accept_offer):
    e_offer = getattr(market, offer)(20, 10, 'A', 'A')
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


def test_balancing_market_negative_offer_trade(market=BalancingMarket(
    bc=NonBlockchainInterface(str(uuid4())), time_slot=now())):  # NOQA
    offer = market.balancing_offer(20, -10, 'A', 'A')

    now = DateTime.now(tz=TIME_ZONE)
    trade = market.accept_offer(offer, 'B', time=now, energy=-10)
    assert trade
    assert trade == market.trades[0]
    assert trade.id
    assert trade.time == now
    assert trade.offer is offer
    assert trade.seller == 'A'
    assert trade.buyer == 'B'


def test_market_bid_trade(market=TwoSidedMarket(bc=MagicMock(), time_slot=now())):
    bid = market.bid(20, 10, 'A', 'A', original_bid_price=20)
    trade_offer_info = TradeBidOfferInfo(2, 2, 0.5, 0.5, 2)
    trade = market.accept_bid(bid, energy=10, seller='B', trade_offer_info=trade_offer_info)
    assert trade
    assert trade.id == market.trades[0].id
    assert trade.id
    assert trade.offer.price == bid.price
    assert trade.offer.energy == bid.energy
    assert trade.seller == 'B'
    assert trade.buyer == 'A'
    assert not trade.residual


@pytest.mark.parametrize("market, offer, accept_offer", [
    (OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
     "offer", "accept_offer"),
    (BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
     "balancing_offer", "accept_offer")
])
def test_market_trade_by_id(market, offer, accept_offer):
    e_offer = getattr(market, offer)(20, 10, 'A', 'A')
    now = DateTime.now(tz=TIME_ZONE)
    trade = getattr(market, accept_offer)(offer_or_id=e_offer.id, buyer='B',
                                          energy=10, time=now)
    assert trade


@pytest.mark.parametrize("market, offer, accept_offer", [
    (OneSidedMarket(bc=MagicMock(), time_slot=now()),
     "offer", "accept_offer"),
    (BalancingMarket(bc=MagicMock(), time_slot=now()),
     "balancing_offer", "accept_offer")
])
def test_market_trade_readonly(market, offer, accept_offer):
    e_offer = getattr(market, offer)(20, 10, 'A', 'A')
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        getattr(market, accept_offer)(e_offer, 'B')


@pytest.mark.parametrize("market, offer, accept_offer", [
    (OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
     "offer", "accept_offer"),
    (BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
     "balancing_offer", "accept_offer")
])
def test_market_trade_not_found(market, offer, accept_offer):
    e_offer = getattr(market, offer)(20, 10, 'A', 'A')

    assert getattr(market, accept_offer)(offer_or_id=e_offer, buyer='B', energy=10)
    with pytest.raises(OfferNotFoundException):
        getattr(market, accept_offer)(offer_or_id=e_offer, buyer='B', energy=10)


def test_market_trade_bid_not_found(
        market=TwoSidedMarket(bc=MagicMock(), time_slot=now())):
    bid = market.bid(20, 10, 'A', 'A')
    trade_offer_info = TradeBidOfferInfo(2, 2, 1, 1, 2)
    assert market.accept_bid(bid, 10, 'B', trade_offer_info=trade_offer_info)

    with pytest.raises(BidNotFound):
        market.accept_bid(bid, 10, 'B', trade_offer_info=trade_offer_info)


@pytest.mark.parametrize("market, offer, accept_offer", [
    (OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
     "offer", "accept_offer"),
    (BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
     "balancing_offer", "accept_offer")
])
def test_market_trade_partial(market, offer, accept_offer):
    e_offer = getattr(market, offer)(20, 20, 'A', 'A')

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


def test_market_trade_bid_partial(market=TwoSidedMarket(bc=MagicMock(), time_slot=now())):
    bid = market.bid(20, 20, 'A', 'A', original_bid_price=20)
    trade_offer_info = TradeBidOfferInfo(1, 1, 1, 1, 1)
    trade = market.accept_bid(bid, energy=5, seller='B', trade_offer_info=trade_offer_info)
    assert trade
    assert trade.id == market.trades[0].id
    assert trade.id
    assert trade.offer is not bid
    assert trade.offer.energy == 5
    assert trade.offer.price == 5
    assert trade.seller == 'B'
    assert trade.buyer == 'A'
    assert trade.residual
    assert len(market.bids) == 1
    assert trade.residual.id in market.bids
    assert market.bids[trade.residual.id].energy == 15
    assert isclose(market.bids[trade.residual.id].price, 15)
    assert market.bids[trade.residual.id].buyer == 'A'


def test_market_accept_bid_emits_bid_split_on_partial_bid(
        called, market=TwoSidedMarket(bc=MagicMock(), time_slot=now())):
    market.add_listener(called)
    bid = market.bid(20, 20, 'A', 'A')
    trade_offer_info = TradeBidOfferInfo(1, 1, 1, 1, 1)
    trade = market.accept_bid(bid, energy=1, trade_offer_info=trade_offer_info)
    assert all([ev != repr(MarketEvent.BID_DELETED) for c in called.calls for ev in c[0]])
    assert len(called.calls) == 2
    assert called.calls[0][0] == (repr(MarketEvent.BID_SPLIT),)
    assert called.calls[1][0] == (repr(MarketEvent.BID_TRADED),)
    assert called.calls[1][1] == {
        'market_id': repr(market.id),
        'bid_trade': repr(trade),
    }


@pytest.mark.parametrize('market_method', ('_update_accumulated_trade_price_energy',
                                           '_update_min_max_avg_trade_prices'))
def test_market_accept_bid_always_updates_trade_stats(
        called, market_method, market=TwoSidedMarket(bc=MagicMock(), time_slot=now())):
    setattr(market, market_method, called)

    bid = market.bid(20, 20, 'A', 'A')
    trade_offer_info = TradeBidOfferInfo(1, 1, 1, 1, 1)
    trade = market.accept_bid(bid, energy=5, seller='B', trade_offer_info=trade_offer_info)
    assert trade
    assert len(getattr(market, market_method).calls) == 1


@pytest.mark.parametrize("market, offer, accept_offer, energy, exception", [
    (OneSidedMarket(bc=MagicMock(), time_slot=now()),
     "offer", "accept_offer", 0, InvalidTrade),
    (OneSidedMarket(bc=MagicMock(), time_slot=now()),
     "offer", "accept_offer", 21, InvalidTrade),
    (BalancingMarket(bc=MagicMock(), time_slot=now()),
     "balancing_offer", "accept_offer", 0,
     InvalidBalancingTradeException),
    (BalancingMarket(bc=MagicMock(), time_slot=now()),
     "balancing_offer", "accept_offer", 21,
     InvalidBalancingTradeException)
])
def test_market_trade_partial_invalid(market, offer, accept_offer, energy, exception):
    e_offer = getattr(market, offer)(20, 20, 'A', 'A')
    with pytest.raises(exception):
        getattr(market, accept_offer)(offer_or_id=e_offer, buyer='B', energy=energy)


@pytest.mark.parametrize('energy', (0, 21, 100, -20))
def test_market_trade_partial_bid_invalid(
        energy, market=TwoSidedMarket(bc=MagicMock(), time_slot=now())):
    bid = market.bid(20, 20, 'A', 'A')
    trade_offer_info = TradeBidOfferInfo(1, 1, 1, 1, 1)
    with pytest.raises(InvalidTrade):
        market.accept_bid(bid, energy=energy, seller='A', trade_offer_info=trade_offer_info)


def test_market_acct_simple(market=OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())),
                                                  time_slot=now())):
    offer = market.offer(20, 10, 'A', 'A')
    market.accept_offer(offer, 'B')

    assert market.traded_energy['A'] == offer.energy
    assert market.traded_energy['B'] == -offer.energy
    assert market.bought_energy('A') == 0
    assert market.bought_energy('B') == offer.energy
    assert market.sold_energy('A') == offer.energy
    assert market.sold_energy('B') == 0


def test_market_acct_multiple(market=OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())),
                                                    time_slot=now())):
    offer1 = market.offer(10, 20, 'A', 'A')
    offer2 = market.offer(10, 10, 'A', 'A')
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
    (OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "offer"),
    (BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "balancing_offer")
])
def test_market_avg_offer_price(market, offer):
    getattr(market, offer)(1, 1, 'A', 'A')
    getattr(market, offer)(3, 1, 'A', 'A')

    assert market.avg_offer_price == 2


@pytest.mark.parametrize("market",
                         [OneSidedMarket(bc=MagicMock(), time_slot=now()),
                          BalancingMarket(bc=MagicMock(), time_slot=now())])
def test_market_avg_offer_price_empty(market):
    assert market.avg_offer_price == 0


@pytest.mark.parametrize("market, offer", [
    (OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "offer"),
    (BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "balancing_offer")
])
def test_market_sorted_offers(market, offer):
    getattr(market, offer)(5, 1, 'A', 'A')
    getattr(market, offer)(3, 1, 'A', 'A')
    getattr(market, offer)(1, 1, 'A', 'A')
    getattr(market, offer)(2, 1, 'A', 'A')
    getattr(market, offer)(4, 1, 'A', 'A')

    assert [o.price for o in market.sorted_offers] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("market, offer", [
    (OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "offer"),
    (BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "balancing_offer")
])
def test_market_most_affordable_offers(market, offer):
    getattr(market, offer)(5, 1, 'A', 'A')
    getattr(market, offer)(3, 1, 'A', 'A')
    getattr(market, offer)(1, 1, 'A', 'A')
    getattr(market, offer)(10, 10, 'A', 'A')
    getattr(market, offer)(20, 20, 'A', 'A')
    getattr(market, offer)(20000, 20000, 'A', 'A')
    getattr(market, offer)(2, 1, 'A', 'A')
    getattr(market, offer)(4, 1, 'A', 'A')

    assert {o.price for o in market.most_affordable_offers} == {1, 10, 20, 20000}


@pytest.mark.parametrize("market, offer", [
    (OneSidedMarket, "offer"),
    (BalancingMarket, "balancing_offer")
])
def test_market_listeners_init(market, offer, called):
    markt = market(bc=MagicMock(), time_slot=now(), notification_listener=called)
    getattr(markt, offer)(10, 20, 'A', 'A')
    assert len(called.calls) == 1


@pytest.mark.parametrize("market, offer, add_listener", [
    (OneSidedMarket(bc=MagicMock(), time_slot=now()), "offer", "add_listener"),
    (BalancingMarket(bc=MagicMock(), time_slot=now()), "balancing_offer", "add_listener")
])
def test_market_listeners_add(market, offer, add_listener, called):
    getattr(market, add_listener)(called)
    getattr(market, offer)(10, 20, 'A', 'A')

    assert len(called.calls) == 1


@pytest.mark.parametrize("market, offer, add_listener, event", [
    (OneSidedMarket(bc=MagicMock(), time_slot=now()),
     "offer", "add_listener", MarketEvent.OFFER),
    (BalancingMarket(bc=MagicMock(), time_slot=now()),
     "balancing_offer", "add_listener", MarketEvent.BALANCING_OFFER)
])
def test_market_listeners_offer(market, offer, add_listener, event, called):
    getattr(market, add_listener)(called)
    e_offer = getattr(market, offer)(10, 20, 'A', 'A')
    assert len(called.calls) == 1
    assert called.calls[0][0] == (repr(event), )
    assert called.calls[0][1] == {'offer': repr(e_offer), 'market_id': repr(market.id)}


@pytest.mark.parametrize("market, offer, accept_offer, add_listener, event", [
    (OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
     "offer", "accept_offer", "add_listener",
     MarketEvent.OFFER_SPLIT),
    (BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
     "balancing_offer", "accept_offer", "add_listener",
     MarketEvent.BALANCING_OFFER_SPLIT)
])
def test_market_listeners_offer_split(market, offer, accept_offer, add_listener, event, called):
    getattr(market, add_listener)(called)
    e_offer = getattr(market, offer)(10., 20, 'A', 'A')
    getattr(market, accept_offer)(e_offer, 'B', energy=3.)
    assert len(called.calls) == 3
    assert called.calls[1][0] == (repr(event), )
    call_kwargs = called.calls[1][1]
    call_kwargs.pop('market_id', None)
    a_offer = deepcopy(e_offer)
    a_offer.price = e_offer.price / 20 * 3
    a_offer.energy = e_offer.energy / 20 * 3
    assert call_kwargs == {
        'original_offer': repr(e_offer),
        'accepted_offer': repr(a_offer),
        'residual_offer': repr(list(market.offers.values())[0])
    }


@pytest.mark.parametrize("market, offer, delete_offer, add_listener, event", [
    (OneSidedMarket(bc=MagicMock(), time_slot=now()),
     "offer", "delete_offer",
     "add_listener", MarketEvent.OFFER_DELETED),
    (BalancingMarket(bc=MagicMock(), time_slot=now()),
     "balancing_offer", "delete_balancing_offer",
     "add_listener", MarketEvent.BALANCING_OFFER_DELETED)
])
def test_market_listeners_offer_deleted(market, offer, delete_offer, add_listener, event, called):
    getattr(market, add_listener)(called)
    e_offer = getattr(market, offer)(10, 20, 'A', 'A')
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
    market = OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now())
    offer1 = market.offer(10, 20, 'A', 'A')
    offer2 = market.offer(10, 10, 'A', 'A')
    offer3 = market.offer(10, last_offer_size, 'D', 'D')

    market.accept_offer(offer1, 'B')
    market.accept_offer(offer2, 'C')
    market.accept_offer(offer3, 'A')
    assert market.traded_energy['A'] == traded_energy


@pytest.mark.parametrize("market, offer, accept_offer", [
    (OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "offer",
     "accept_offer"),
    (BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "balancing_offer",
     "accept_offer")
])
def test_market_accept_offer_yields_partial_trade(market, offer, accept_offer):
    e_offer = getattr(market, offer)(2.0, 4, 'seller', 'seller')
    trade = getattr(market, accept_offer)(e_offer, 'buyer', energy=1)
    assert trade.offer.id == e_offer.id and trade.offer.energy == 1 and trade.residual.energy == 3


def test_market_accept_bid_yields_partial_bid_trade(
        market=TwoSidedMarket(bc=MagicMock(), time_slot=now())):
    bid = market.bid(2.0, 4, 'buyer', 'buyer')
    trade_offer_info = TradeBidOfferInfo(2, 2, 1, 1, 2)
    trade = market.accept_bid(bid, energy=1, seller='seller', trade_offer_info=trade_offer_info)
    assert trade.offer.id == bid.id and trade.offer.energy == 1


@pytest.yield_fixture
def pac_market():
    return PayAsClearMatcher()


@pytest.mark.parametrize("offer, bid, mcp_rate, mcp_energy", [
    ([1, 2, 3, 4, 5, 6, 7], [1, 2, 3, 4, 5, 6, 7], 4, 4),
    ([1, 2, 3, 4, 5, 6, 7], [7, 6, 5, 4, 3, 2, 1], 4, 4),
    ([8, 9, 10, 11, 12, 13, 14], [8, 9, 10, 11, 12, 13, 14], 11, 4),
    ([2, 3, 3, 5, 6, 7, 8], [1, 2, 3, 4, 5, 6, 7], 5, 3),
    ([10, 10, 10, 10, 10, 10, 10], [1, 2, 3, 4, 10, 10, 10], 10, 3),
    ([1, 2, 5, 5, 5, 6, 7], [5, 5, 5, 5, 5, 5, 5], 5, 5),
    # TODO: Future enhancement story to decide multiple offers
    #  acceptance/rejection having energy_rate equals to clearing_rate
    # ([2, 3, 6, 7, 7, 7, 7], [7, 5, 5, 2, 2, 2, 2], 5, 2),
    # ([2, 2, 4, 4, 4, 4, 6], [6, 6, 6, 6, 2, 2, 2], 4, 4),
])
@pytest.mark.parametrize("algorithm", [1])
def test_double_sided_market_performs_pay_as_clear_matching(pac_market, offer, bid, mcp_rate,
                                                            mcp_energy, algorithm):
    ConstSettings.IAASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM = algorithm
    pac_market.offers = {"offer1": Offer('id1', now(), offer[0], 1, 'other'),
                         "offer2": Offer('id2', now(), offer[1], 1, 'other'),
                         "offer3": Offer('id3', now(), offer[2], 1, 'other'),
                         "offer4": Offer('id4', now(), offer[3], 1, 'other'),
                         "offer5": Offer('id5', now(), offer[4], 1, 'other'),
                         "offer6": Offer('id6', now(), offer[5], 1, 'other'),
                         "offer7": Offer('id7', now(), offer[6], 1, 'other')}

    pac_market.bids = {"bid1": Bid('bid_id1', now(), bid[0], 1, 'B', 'S'),
                       "bid2": Bid('bid_id2', now(), bid[1], 1, 'B', 'S'),
                       "bid3": Bid('bid_id3', now(), bid[2], 1, 'B', 'S'),
                       "bid4": Bid('bid_id4', now(), bid[3], 1, 'B', 'S'),
                       "bid5": Bid('bid_id5', now(), bid[4], 1, 'B', 'S'),
                       "bid6": Bid('bid_id6', now(), bid[5], 1, 'B', 'S'),
                       "bid7": Bid('bid_id7', now(), bid[6], 1, 'B', 'S')}

    matched_rate, matched_energy = pac_market.get_clearing_point(
        pac_market.bids, pac_market.offers, now()
    )
    assert matched_rate == mcp_rate
    assert matched_energy == mcp_energy


def test_double_sided_pay_as_clear_market_works_with_floats(pac_market):
    ConstSettings.IAASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM = 1
    pac_market.offers = {"offer1": Offer('id1', now(), 1.1, 1, 'other'),
                         "offer2": Offer('id2', now(), 2.2, 1, 'other'),
                         "offer3": Offer('id3', now(), 3.3, 1, 'other')}

    pac_market.bids = {
                    "bid1": Bid('bid_id1', now(), 3.3, 1, 'B', 'S'),
                    "bid2": Bid('bid_id2', now(), 2.2, 1, 'B', 'S'),
                    "bid3": Bid('bid_id3', now(), 1.1, 1, 'B', 'S')}

    matched = pac_market.get_clearing_point(pac_market.bids, pac_market.offers, now())[0]
    assert matched == 2.2


@pytest.yield_fixture
def pab_market():
    return FakeTwoSidedPayAsBid()


class MarketStateMachine(RuleBasedStateMachine):
    offers = Bundle('Offers')
    actors = Bundle('Actors')

    def __init__(self):
        self.market = OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now())
        super().__init__()

    @rule(target=actors, actor=st.text(min_size=1, max_size=3,
                                       alphabet=string.ascii_letters + string.digits))
    def new_actor(self, actor):
        return actor

    @rule(target=offers, seller=actors, energy=st.integers(min_value=1),
          price=st.integers(min_value=0))
    def offer(self, seller, energy, price):
        return self.market.offer(price, energy, seller, seller)

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
