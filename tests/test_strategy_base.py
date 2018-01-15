import pytest

from datetime import datetime

from d3a.models.strategy.base import Offers
from d3a.models.market import Offer, Trade


class FakeLog:
    def warn(self, *args):
        pass

    def error(self, *args):
        pass


class FakeOwner:
    @property
    def name(self):
        return 'FakeOwner'


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
    trade = Trade('trade_id', datetime.now(), accepted_offer, offer1.seller, 'buyer')
    offers3.on_offer_changed('market', offer1, residual_offer)
    offers3.on_trade('market', trade)
    assert len(offers3.open_in_market('market')) == 2
    assert len(offers3.sold_in_market('market')) == 1
    assert accepted_offer in offers3.sold_in_market('market')
    assert residual_offer in offers3.open_in_market('market')
