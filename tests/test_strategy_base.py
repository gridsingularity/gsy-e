import pytest

from d3a.models.strategy.base import Offers


class FakeLog:
    def warn(self, *args):
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


@pytest.fixture
def offers():
    fixture = Offers(FakeStrategy())
    fixture.post('id', 'market')
    return fixture


def test_offers_open(offers):
    assert len(offers.open) == 1
    offers.sold['id'] = 'market'
    assert len(offers.open) == 0


def test_offers_replace_open_offer(offers):
    offers.replace('id', 'new_id', 'market')
    assert offers.posted['new_id'] == 'market'
    assert 'id' not in offers.posted


def test_offers_does_not_replace_sold_offer(offers):
    offers.sold['id'] = 'market'
    offers.replace('id', 'new_id', 'market')
    assert 'id' in offers.posted and 'new_id' not in offers.posted


@pytest.fixture
def offers2():
    fixture = Offers(FakeStrategy())
    fixture.post('id', 'market')
    fixture.post('id2', 'market')
    fixture.post('id3', 'market2')
    return fixture


def test_offers_in_market(offers2):
    assert offers2.posted_in_market('market') == ['id', 'id2']
    offers2.sold['id2'] = 'market'
    assert offers2.sold_in_market('market') == ['id2']
    assert offers2.sold_in_market('market2') == []
