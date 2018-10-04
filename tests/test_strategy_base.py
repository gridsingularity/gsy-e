import pytest

import pendulum

from d3a import TIME_ZONE
from d3a.exceptions import MarketException
from d3a.models.strategy.base import BaseStrategy, Offers
from d3a.models.market import Offer, Trade, Bid


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
    @property
    def name(self):
        return 'FakeArea'


class FakeStrategy:
    @property
    def owner(self):
        return FakeOwner()

    @property
    def log(self):
        return FakeLog()


class FakeOffer:
    def __init__(self, id):
        self.id = id


class FakeMarket:
    def __init__(self, *, raises):
        self.raises = raises
        self.bids = {}

    def accept_offer(self, offer, id, *, energy=None, time=None, price_drop=False):
        if self.raises:
            raise MarketException
        else:
            offer.energy = energy
            return Trade('trade', 0, offer, offer.seller, 'FakeOwner')

    def bid(self, price, energy, buyer, seller):
        return Bid(123, price, energy, buyer, seller, self)


@pytest.fixture
def offers():
    fixture = Offers(FakeStrategy())
    fixture.post(FakeOffer('id'), 'market')
    return fixture


def test_offers_open(offers):
    assert len(offers.open) == 1
    offers.sold['market'].append('id')
    assert len(offers.open) == 0


def test_offers_replace_open_offer(offers):
    old_offer = offers.posted_in_market('market')[0]
    new_offer = FakeOffer('new_id')
    offers.replace(old_offer, new_offer, 'market')
    assert offers.posted_in_market('market')[0].id == 'new_id'
    assert 'id' not in offers.posted


def test_offers_does_not_replace_sold_offer(offers):
    old_offer = offers.posted_in_market('market')[0]
    new_offer = FakeOffer('new_id')
    offers.sold_offer('id', 'market')
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
    assert len(offers2.posted_in_market('market')) == 2
    offers2.sold_offer('id2', 'market')
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
    accepted_offer = Offer('id', 1, 1.8, offer1.seller, 'market')
    residual_offer = Offer('new_id', 1, 1.2, offer1.seller, 'market')
    trade = Trade('trade_id', pendulum.now(tz=TIME_ZONE), accepted_offer, offer1.seller, 'buyer')
    offers3.on_offer_changed('market', offer1, residual_offer)
    offers3.on_trade('market', trade)
    assert len(offers3.open_in_market('market')) == 2
    assert len(offers3.sold_in_market('market')) == 1
    assert accepted_offer in offers3.sold_in_market('market')
    assert residual_offer in offers3.open_in_market('market')


@pytest.fixture
def offer_to_accept():
    return Offer('new', 1.0, 0.5, 'someone')


@pytest.fixture
def base():
    base = BaseStrategy()
    base.owner = FakeOwner()
    base.area = FakeArea()
    return base


def test_accept_offer(base, offer_to_accept):
    market = FakeMarket(raises=False)
    base.accept_offer(market, offer_to_accept)
    assert offer_to_accept in base.offers.bought_in_market(market)


def test_accept_partial_offer(base, offer_to_accept):
    market = FakeMarket(raises=False)
    base.accept_offer(market, offer_to_accept, energy=0.1)
    assert base.offers.bought_in_market(market)[0].energy == 0.1


def test_accept_offer_handles_market_exception(base, offer_to_accept):
    market = FakeMarket(raises=True)
    try:
        base.accept_offer(market, offer_to_accept, energy=0.5)
    except MarketException:
        pass
    assert len(base.offers.bought_in_market(market)) == 0


def test_accept_post_bid(base):
    market = FakeMarket(raises=True)

    bid = base.post_bid(market, 10, 5)
    assert base.are_bids_posted(market)
    assert len(base.get_posted_bids(market)) == 1
    assert base.get_posted_bids(market)[0] == bid
    assert bid.energy == 5
    assert bid.price == 10
    assert bid.seller == 'FakeArea'
    assert bid.buyer == 'FakeOwner'


def test_remove_bid_from_pending(base):
    market = FakeMarket(raises=True)

    bid = base.post_bid(market, 10, 5)
    assert base.are_bids_posted(market)

    base.remove_bid_from_pending(bid.id, market)
    assert not base.are_bids_posted(market)


def test_add_bid_to_bought(base):
    market = FakeMarket(raises=True)

    bid = base.post_bid(market, 10, 5)
    assert base.are_bids_posted(market)

    base.add_bid_to_bought(bid, market)
    assert not base.are_bids_posted(market)
    assert len(base.get_traded_bids_from_market(market)) == 1
    assert base.get_traded_bids_from_market(market) == [bid]
