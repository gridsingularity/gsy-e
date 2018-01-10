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
