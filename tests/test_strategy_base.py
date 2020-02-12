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
import pytest
from unittest.mock import MagicMock
import pendulum

from d3a.constants import TIME_ZONE
from d3a.d3a_core.exceptions import MarketException
from d3a.models.strategy import BidEnabledStrategy, Offers
from d3a.models.market.market_structures import Offer, Trade, Bid
from d3a_interface.constants_limits import ConstSettings


def teardown_function():
    ConstSettings.IAASettings.MARKET_TYPE = 1


class FakeLog:
    def warning(self, *args):
        pass

    def error(self, *args):
        pass


class FakeOwner:
    @property
    def name(self):
        return 'FakeOwner'


class FakeArea:
    def __init__(self, market=None):
        self._market = market

    def get_future_market_from_id(self, market_id):
        return self._market

    @property
    def name(self):
        return 'FakeArea'


class FakeStrategy:
    @property
    def owner(self):
        return FakeOwner()

    @property
    def area(self):
        return FakeOwner()

    @property
    def log(self):
        return FakeLog()


class FakeOffer:
    def __init__(self, id):
        self.id = id


class FakeMarket:
    def __init__(self, *, raises, id="11"):
        self.raises = raises
        self.transfer_fee_ratio = 0
        self.bids = {}
        self.id = id

    def accept_offer(self, offer_or_id, *, buyer="", energy=None, time=None, already_tracked=False,
                     trade_rate: float = None, trade_bid_info=None, buyer_origin=None):
        offer = offer_or_id
        if self.raises:
            raise MarketException
        else:
            if energy is None:
                energy = offer.energy
            offer.energy = energy
            return Trade('trade', 0, offer, offer.seller, 'FakeOwner',
                         seller_origin=offer.seller_origin, buyer_origin=buyer_origin)

    def bid(self, price, energy, buyer, seller, original_bid_price=None,
            buyer_origin=None):
        return Bid(123, price, energy, buyer, seller, original_bid_price,
                   buyer_origin=buyer_origin)


@pytest.fixture
def offers():
    market = FakeMarket(raises=False, id='market')
    fixture = Offers(FakeStrategy())
    fixture.post(FakeOffer('id'), market.id)
    fixture.__fake_market = market
    return fixture


def test_offers_open(offers):
    assert len(offers.open) == 1
    market = offers.__fake_market
    old_offer = offers.posted_in_market(market.id)[0]
    offers.sold_offer(old_offer, 'market')
    assert len(offers.open) == 0


def test_offers_replace_open_offer(offers):
    market = offers.__fake_market
    old_offer = offers.posted_in_market(market.id)[0]
    new_offer = FakeOffer('new_id')
    offers.replace(old_offer, new_offer, market.id)
    assert offers.posted_in_market(market.id)[0].id == 'new_id'
    assert 'id' not in offers.posted


def test_offers_does_not_replace_sold_offer(offers):
    old_offer = offers.posted_in_market('market')[0]
    new_offer = FakeOffer('new_id')
    offers.sold_offer(old_offer, 'market')
    offers.replace(old_offer, new_offer, 'market')
    assert old_offer in offers.posted and new_offer not in offers.posted


@pytest.fixture
def offers2():
    fixture = Offers(FakeStrategy())
    fixture.post(FakeOffer('id'), 'market')
    fixture.post(FakeOffer('id2'), 'market')
    fixture.post(FakeOffer('id3'), 'market2')
    return fixture


def test_offers_in_market(offers2):
    old_offer = next(o for o in offers2.posted_in_market('market') if o.id == "id2")
    assert len(offers2.posted_in_market('market')) == 2
    offers2.sold_offer(old_offer, 'market')
    assert len(offers2.sold_in_market('market')) == 1
    assert len(offers2.sold_in_market('market2')) == 0


@pytest.fixture
def offer1():
    return Offer('id', 1, 3, 'FakeOwner', 'market')


@pytest.fixture
def offers3(offer1):
    fixture = Offers(FakeStrategy())
    fixture.post(offer1, 'market')
    fixture.post(Offer('id2', 1, 1, 'FakeOwner', 'market'), 'market')
    fixture.post(Offer('id3', 1, 1, 'FakeOwner', 'market2'), 'market2')
    return fixture


def test_offers_partial_offer(offer1, offers3):
    accepted_offer = Offer('id', 1, 0.6, offer1.seller, 'market')
    residual_offer = Offer('new_id', 1, 1.2, offer1.seller, 'market')
    offers3.on_offer_split(offer1, accepted_offer, residual_offer, 'market')
    trade = Trade('trade_id', pendulum.now(tz=TIME_ZONE), accepted_offer, offer1.seller, 'buyer')
    offers3.on_trade('market', trade)
    assert len(offers3.sold_in_market('market')) == 1
    assert accepted_offer in offers3.sold_in_market('market')


@pytest.fixture
def offer_to_accept():
    return Offer('new', 1.0, 0.5, 'someone')


@pytest.fixture
def base():
    base = BidEnabledStrategy()
    base.owner = FakeOwner()
    base.area = FakeArea()
    return base


def test_accept_offer(base, offer_to_accept):
    market = FakeMarket(raises=False)
    base.accept_offer(market, offer_to_accept)
    assert offer_to_accept in base.offers.bought.keys()
    assert market.id == base.offers.bought[offer_to_accept].id


def test_accept_partial_offer(base, offer_to_accept):
    market = FakeMarket(raises=False)
    base.accept_offer(market, offer_to_accept, energy=0.1)

    assert list(base.offers.bought.keys())[0].energy == 0.1


def test_accept_offer_handles_market_exception(base, offer_to_accept):
    market = FakeMarket(raises=True)
    try:
        base.accept_offer(market, offer_to_accept, energy=0.5)
    except MarketException:
        pass
    assert len(base.offers.bought.keys()) == 0


def test_accept_post_bid(base):
    market = FakeMarket(raises=True)

    bid = base.post_bid(market, 10, 5)
    assert base.are_bids_posted(market.id)
    assert len(base.get_posted_bids(market)) == 1
    assert base.get_posted_bids(market)[0] == bid
    assert bid.energy == 5
    assert bid.price == 10
    assert bid.seller == 'FakeArea'
    assert bid.buyer == 'FakeOwner'


def test_remove_bid_from_pending(base):
    market = FakeMarket(raises=True)
    base.area._market = market
    bid = base.post_bid(market, 10, 5)
    assert base.are_bids_posted(market.id)

    base.remove_bid_from_pending(bid.id, market.id)
    assert not base.are_bids_posted(market.id)


def test_add_bid_to_bought(base):
    market = FakeMarket(raises=True)
    base.area._market = market
    bid = base.post_bid(market, 10, 5)
    assert base.are_bids_posted(market.id)

    base.add_bid_to_bought(bid, market.id)
    assert not base.are_bids_posted(market.id)
    assert len(base.get_traded_bids_from_market(market)) == 1
    assert base.get_traded_bids_from_market(market) == [bid]


def test_bid_events_fail_for_one_sided_market(base):
    ConstSettings.IAASettings.MARKET_TYPE = 1
    test_bid = Bid("123", 12, 23, 'A', 'B')
    with pytest.raises(AssertionError):
        base.event_bid_traded(market_id=123, bid_trade=test_bid)
    with pytest.raises(AssertionError):
        base.event_bid_deleted(market_id=123, bid=test_bid)
    with pytest.raises(AssertionError):
        base.event_bid_split(market_id=123, original_bid=test_bid, accepted_bid=test_bid,
                             residual_bid=test_bid)


def test_bid_deleted_removes_bid_from_posted(base):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    test_bid = Bid("123", 12, 23, base.owner.name, 'B')
    market = FakeMarket(raises=False, id=21)
    base.area._market = market
    base._bids[market.id] = [test_bid]
    base.event_bid_deleted(market_id=21, bid=test_bid)
    assert base.get_posted_bids(market) == []


def test_bid_split_adds_bid_to_posted(base):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    test_bid = Bid("123", 12, 12, base.owner.name, 'B')
    accepted_bid = Bid("123", 8, 8, base.owner.name, 'B')
    residual_bid = Bid("456", 4, 4, base.owner.name, 'B')
    market = FakeMarket(raises=False, id=21)
    base.area._market = market
    base._bids[market.id] = []
    base.event_bid_split(market_id=21, original_bid=test_bid, accepted_bid=accepted_bid,
                         residual_bid=residual_bid)
    assert base.get_posted_bids(market) == [accepted_bid, residual_bid]


def test_bid_traded_moves_bid_from_posted_to_traded(base):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    test_bid = Bid("123", 12, 23, base.owner.name, 'B')
    trade = MagicMock()
    trade.buyer = base.owner.name
    trade.offer = test_bid
    market = FakeMarket(raises=False, id=21)
    base.area._market = market
    base._bids[market.id] = [test_bid]
    base.event_bid_traded(market_id=21, bid_trade=trade)
    assert base.get_posted_bids(market) == []
    assert base.get_traded_bids_from_market(market) == [test_bid]
