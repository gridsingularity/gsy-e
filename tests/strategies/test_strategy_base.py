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

from unittest.mock import MagicMock
from uuid import uuid4

import pendulum
import pytest
from gsy_framework.constants_limits import ConstSettings

from d3a.constants import TIME_ZONE
from d3a.gsy_e_core.blockchain_interface import NonBlockchainInterface
from d3a.gsy_e_core.exceptions import MarketException
from gsy_framework.data_classes import Offer, Trade, Bid
from d3a.models.market.one_sided import OneSidedMarket
from d3a.models.market.two_sided import TwoSidedMarket
from d3a.models.strategy import BidEnabledStrategy, Offers, BaseStrategy


def teardown_function():
    ConstSettings.IAASettings.MARKET_TYPE = 1


class FakeLog:
    def warning(self, *args):
        pass

    def error(self, *args):
        pass


class FakeOwner:

    def __init__(self):
        self.uuid = str(uuid4())

    @property
    def name(self):
        return 'FakeOwner'


class FakeArea:
    def __init__(self, market=None):
        self._market = market
        self.uuid = str(uuid4())

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
        self.time_slot = pendulum.now()

    def accept_offer(self, offer_or_id, *, buyer="", energy=None, time=None, already_tracked=False,
                     trade_rate: float = None, trade_bid_info=None, buyer_origin=None,
                     buyer_origin_id=None, buyer_id=None):
        offer = offer_or_id
        if self.raises:
            raise MarketException
        else:
            if energy is None:
                energy = offer.energy
            offer.energy = energy
            return Trade('trade', 0, offer, offer.seller, 'FakeOwner',
                         seller_origin=offer.seller_origin, buyer_origin=buyer_origin,
                         buyer_origin_id=buyer_origin_id, buyer_id=buyer_id)

    def bid(self, price, energy, buyer, original_price=None,
            buyer_origin=None, buyer_origin_id=None, buyer_id=None,
            attributes=None, requirements=None, time_slot=None):
        return Bid(123, pendulum.now(), price, energy, buyer, original_price,
                   buyer_origin=buyer_origin, buyer_origin_id=buyer_origin_id,
                   buyer_id=buyer_id, attributes=attributes, requirements=requirements,
                   time_slot=time_slot)


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
    return Offer('id', pendulum.now(), 1, 3, 'FakeOwner', 'market')


@pytest.fixture
def offers3(offer1):
    fixture = Offers(FakeStrategy())
    fixture.post(offer1, 'market')
    fixture.post(Offer('id2', pendulum.now(), 1, 1, 'FakeOwner', 'market'), 'market')
    fixture.post(Offer('id3', pendulum.now(), 1, 1, 'FakeOwner', 'market2'), 'market2')
    return fixture


def test_offers_partial_offer(offer1, offers3):
    accepted_offer = Offer('id', pendulum.now(), 1, 0.6, offer1.seller, 'market')
    residual_offer = Offer('new_id', pendulum.now(), 1, 1.2, offer1.seller, 'market')
    offers3.on_offer_split(offer1, accepted_offer, residual_offer, 'market')
    trade = Trade('trade_id', pendulum.now(tz=TIME_ZONE), accepted_offer, offer1.seller, 'buyer')
    offers3.on_trade('market', trade)
    assert len(offers3.sold_in_market('market')) == 1
    assert accepted_offer in offers3.sold_in_market('market')


@pytest.fixture
def offer_to_accept():
    return Offer('new', pendulum.now(), 1.0, 0.5, 'someone')


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
    assert market.id == base.offers.bought[offer_to_accept]


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
    assert bid.buyer == 'FakeOwner'


def test_remove_bid_from_pending(base):
    market = FakeMarket(raises=True)
    base.area._market = market
    bid = base.post_bid(market, 10, 5)
    assert base.are_bids_posted(market.id)

    base.remove_bid_from_pending(market.id, bid.id)
    assert not base.are_bids_posted(market.id)


def test_add_bid_to_bought(base):
    market = FakeMarket(raises=True)
    base.area._market = market
    bid = base.post_bid(market, 10, 5)
    assert base.are_bids_posted(market.id)

    base.add_bid_to_bought(bid, market.id)
    assert not base.are_bids_posted(market.id)
    assert len(base._get_traded_bids_from_market(market.id)) == 1
    assert base._get_traded_bids_from_market(market.id) == [bid]


def test_bid_events_fail_for_one_sided_market(base):
    ConstSettings.IAASettings.MARKET_TYPE = 1
    test_bid = Bid("123", pendulum.now(), 12, 23, 'A', 'B')
    with pytest.raises(AssertionError):
        base.event_bid_traded(market_id=123, bid_trade=test_bid)
    with pytest.raises(AssertionError):
        base.event_bid_deleted(market_id=123, bid=test_bid)
    with pytest.raises(AssertionError):
        base.event_bid_split(market_id=123, original_bid=test_bid, accepted_bid=test_bid,
                             residual_bid=test_bid)


def test_bid_deleted_removes_bid_from_posted(base):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    test_bid = Bid("123", pendulum.now(), 12, 23, base.owner.name, 'B')
    market = FakeMarket(raises=False, id=21)
    base.area._market = market
    base._bids[market.id] = [test_bid]
    base.event_bid_deleted(market_id=21, bid=test_bid)
    assert base.get_posted_bids(market) == []


def test_bid_split_adds_bid_to_posted(base):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    test_bid = Bid("123", pendulum.now(), 12, 12, base.owner.name, 'B')
    accepted_bid = Bid("123", pendulum.now(), 8, 8, base.owner.name, 'B')
    residual_bid = Bid("456", pendulum.now(), 4, 4, base.owner.name, 'B')
    market = FakeMarket(raises=False, id=21)
    base.area._market = market
    base._bids[market.id] = []
    base.event_bid_split(market_id=21, original_bid=test_bid, accepted_bid=accepted_bid,
                         residual_bid=residual_bid)
    assert base.get_posted_bids(market) == [accepted_bid, residual_bid]


def test_bid_traded_moves_bid_from_posted_to_traded(base):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    test_bid = Bid("123", pendulum.now(), 12, 23, base.owner.name, 'B')
    trade = MagicMock()
    trade.buyer = base.owner.name
    trade.offer_bid = test_bid
    market = FakeMarket(raises=False, id=21)
    base.area._market = market
    base._bids[market.id] = [test_bid]
    base.event_bid_traded(market_id=21, bid_trade=trade)
    assert base.get_posted_bids(market) == []
    assert base._get_traded_bids_from_market(market.id) == [test_bid]


@pytest.mark.parametrize('market_class', [OneSidedMarket, TwoSidedMarket])
def test_can_offer_be_posted(market_class):
    base = BaseStrategy()
    base.owner = FakeOwner()
    base.area = FakeArea()

    market = market_class(time_slot=pendulum.now())

    base.offers.post(Offer('id', pendulum.now(), price=1, energy=12, seller='A'), market.id)
    base.offers.post(Offer('id2', pendulum.now(), price=1, energy=13, seller='A'), market.id)
    base.offers.post(Offer('id3', pendulum.now(), price=1, energy=20, seller='A'), market.id)

    assert base.can_offer_be_posted(4.999, 1, 50, market) is True
    assert base.can_offer_be_posted(5.0, 1, 50, market) is True
    assert base.can_offer_be_posted(5.001, 1, 50, market) is False


@pytest.mark.parametrize('market_class', [TwoSidedMarket])
def test_can_bid_be_posted(market_class, base):
    market = market_class(time_slot=pendulum.now())

    base.post_bid(market, price=1, energy=23, replace_existing=False)
    base.post_bid(market, price=1, energy=27, replace_existing=False)
    base.post_bid(market, price=1, energy=10, replace_existing=False)

    assert base.can_bid_be_posted(9.999, 1, 70, market) is True
    assert base.can_bid_be_posted(10.0, 1, 70, market) is True
    assert base.can_bid_be_posted(10.001, 1, 70, market) is False


@pytest.mark.parametrize('market_class', [TwoSidedMarket])
def test_post_bid_with_replace_existing(market_class, base):
    """Calling post_bid with replace_existing=True triggers the removal of the existing bids."""

    market = market_class(time_slot=pendulum.now())
    base.area._market = market

    _ = base.post_bid(market, 10, 5, replace_existing=False)
    _ = base.post_bid(market, 12, 6, replace_existing=False)
    bid_3 = base.post_bid(market, 8, 4, replace_existing=True)
    bid_4 = base.post_bid(market, 4, 2, replace_existing=False)

    assert base.get_posted_bids(market) == [bid_3, bid_4]


@pytest.mark.parametrize('market_class', [TwoSidedMarket])
def test_post_bid_without_replace_existing(market_class, base):
    """Calling post_bid with replace_existing=False does not trigger the removal of the existing
    bids.
    """
    market = market_class(time_slot=pendulum.now())
    base.area._market = market

    bid_1 = base.post_bid(market, 10, 5, replace_existing=False)
    bid_2 = base.post_bid(market, 12, 6, replace_existing=False)
    bid_3 = base.post_bid(market, 8, 4, replace_existing=False)

    assert base.get_posted_bids(market) == [bid_1, bid_2, bid_3]


@pytest.mark.parametrize('market_class', [OneSidedMarket, TwoSidedMarket])
def test_post_offer_creates_offer_with_correct_parameters(market_class):
    """Calling post_offer with replace_existing=False does not trigger the removal of the existing
    offers.
    """
    strategy = BaseStrategy()
    strategy.owner = FakeOwner()
    strategy.area = FakeArea()

    market = market_class(bc=NonBlockchainInterface(str(uuid4())), time_slot=pendulum.now())
    strategy.area._market = market

    offer_args = {
        'price': 1, 'energy': 1, 'seller': 'seller-name', 'seller_origin': 'seller-origin-name'}

    offer = strategy.post_offer(market, replace_existing=False, **offer_args)

    # The offer is created with the expected parameters
    assert offer.price == 1
    assert offer.energy == 1
    assert offer.seller == 'seller-name'
    assert offer.seller_origin == 'seller-origin-name'


@pytest.mark.parametrize('market_class', [OneSidedMarket, TwoSidedMarket])
def test_post_offer_with_replace_existing(market_class):
    """Calling post_offer with replace_existing triggers the removal of the existing offers."""

    strategy = BaseStrategy()
    strategy.owner = FakeOwner()
    strategy.area = FakeArea()

    market = market_class(bc=NonBlockchainInterface(str(uuid4())), time_slot=pendulum.now())
    strategy.area._market = market

    # Post a first offer on the market
    offer_1_args = {
        'price': 1, 'energy': 1, 'seller': 'seller-name', 'seller_origin': 'seller-origin-name'}
    offer = strategy.post_offer(market, replace_existing=False, **offer_1_args)
    assert strategy.offers.open_in_market(market.id) == [offer]

    # Post a new offer not replacing the previous ones
    offer_2_args = {
        'price': 1, 'energy': 1, 'seller': 'seller-name', 'seller_origin': 'seller-origin-name'}
    offer_2 = strategy.post_offer(market, replace_existing=False, **offer_2_args)
    assert strategy.offers.open_in_market(market.id) == [offer, offer_2]

    # Post a new offer replacing the previous ones (default behavior)
    offer_3_args = {
        'price': 1, 'energy': 1, 'seller': 'seller-name', 'seller_origin': 'seller-origin-name'}
    offer_3 = strategy.post_offer(market, **offer_3_args)
    assert strategy.offers.open_in_market(market.id) == [offer_3]


def test_energy_traded_and_cost_traded(base):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    market = FakeMarket(raises=True)
    base.area._market = market
    o1 = Offer('id', pendulum.now(), price=1, energy=23, seller='A')
    o2 = Offer('id2', pendulum.now(), price=1, energy=27, seller='A')
    o3 = Offer('id3', pendulum.now(), price=1, energy=10, seller='A')
    base.offers.sold_offer(o1, market.id)
    base.offers.sold_offer(o2, market.id)
    base.offers.sold_offer(o3, market.id)
    assert base.energy_traded(market.id) == 60
    assert base.energy_traded_costs(market.id) == 3
    b1 = base.post_bid(market, 1, 23)
    b2 = base.post_bid(market, 1, 27)
    b3 = base.post_bid(market, 1, 10)
    base.add_bid_to_bought(b1, market.id)
    base.add_bid_to_bought(b2, market.id)
    base.add_bid_to_bought(b3, market.id)
    # energy and costs get accumulated from both offers and bids
    assert base.energy_traded(market.id) == 120
    assert base.energy_traded_costs(market.id) == 6
