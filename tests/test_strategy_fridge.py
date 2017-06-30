import pytest

from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market import Offer
from d3a.models.strategy.const import FRIDGE_MIN_NEEDED_ENERGY
from d3a.models.strategy.fridge import FridgeStrategy


class FakeArea():
    def __init__(self):
        self.appliance = None
        self.name = 'FakeArea'

    @property
    def config(self):
        return DEFAULT_CONFIG

    @property
    def current_tick(self):
        return 5

    @property
    def historical_avg_price(self):
        return 30

    @property
    def historical_min_max_price(self):
        return 30, 30


class FakeMarket:
    @property
    def sorted_offers(self):
        return [
            Offer('id', (10 * (FRIDGE_MIN_NEEDED_ENERGY / 1000)),
                  (FRIDGE_MIN_NEEDED_ENERGY / 1000), 'A', self)
        ]


@pytest.fixture
def market():
    return FakeMarket()


@pytest.fixture
def area():
    return FakeArea()


@pytest.fixture
def fridge_strategy(market, area, called):
    f = FridgeStrategy()
    f.next_market = market
    f.owner = area
    f.area = area
    f.accept_offer = called
    return f


def test_fridge_accept_offer(fridge_strategy, area, market):
    fridge_strategy.event_tick(area=area)
    assert fridge_strategy.accept_offer.calls[0][0][1] == repr(market.sorted_offers[0])
