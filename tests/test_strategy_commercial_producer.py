import pytest

from d3a.models.market import Offer, Trade
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.const import COMMERCIAL_OFFERS
from d3a.models.area import DEFAULT_CONFIG


class FakeArea():
    def __init__(self, count):
        self.current_tick = 2
        self.appliance = None
        self.name = 'FakeArea'
        self.test_market = FakeMarket(0)

    @property
    def markets(self):
        return {"now": self.test_market}

    @property
    def config(self):
        return DEFAULT_CONFIG


class FakeMarket:
    def __init__(self, count):
        self.count = count
        self.created_offers = []

    def offer(self, price, energy, seller, market=None):
        offer = Offer('id', price, energy, seller, market)
        self.created_offers.append(offer)
        offer.id = 'id'
        return offer


"""TEST1"""


@pytest.fixture()
def area_test1():
    return FakeArea(0)


@pytest.fixture()
def commercial_test1(area_test1):
    c = CommercialStrategy()
    c.area = area_test1
    c.owner = area_test1
    return c


def testing_event_activate(commercial_test1, area_test1):
    commercial_test1.event_activate()
    assert len(area_test1.test_market.created_offers) == COMMERCIAL_OFFERS
    (min_energy, max_energy) = commercial_test1.energy_range_wh
    for i in range(COMMERCIAL_OFFERS - 1):
        assert area_test1.test_market.created_offers[i].energy <= max_energy / 1000
        assert area_test1.test_market.created_offers[i].energy >= min_energy / 1000


"""TEST2"""


@pytest.fixture()
def area_test2():
    return FakeArea(0)


@pytest.fixture()
def commercial_test2(area_test2):
    c = CommercialStrategy()
    c.area = area_test2
    c.owner = area_test2
    return c


def test_event_trade(area_test2, commercial_test2):
    commercial_test2.event_activate()
    commercial_test2.event_trade(market=area_test2.test_market,
                                 trade=Trade(id='id',
                                             time='time',
                                             offer=Offer(
                                                 id='id', price=20, energy=1, seller='FakeArea',
                                             ),
                                             seller='FakeArea',
                                             buyer='buyer'
                                             )
                                 )
    assert len(area_test2.test_market.created_offers) == 21


"""TEST3"""


@pytest.fixture()
def area_test3():
    return FakeArea(0)


@pytest.fixture()
def commercial_test3(area_test3):
    c = CommercialStrategy()
    c.area = area_test3
    c.owner = area_test3
    return c


def testing_event_market_cycle(commercial_test3, area_test3):
    commercial_test3.event_activate()
    commercial_test3.event_market_cycle()
    assert len(area_test3.test_market.created_offers) == 2*COMMERCIAL_OFFERS
    (min_energy, max_energy) = commercial_test3.energy_range_wh
    for i in range(COMMERCIAL_OFFERS - 1):
        assert area_test3.test_market.created_offers[i].energy <= max_energy / 1000
        assert area_test3.test_market.created_offers[i].energy >= min_energy / 1000


def test_commercial_producer_constructor_rejects_invalid_parameters():
    with pytest.raises(TypeError):
        CommercialStrategy(energy_range_wh=-1)
    with pytest.raises(ValueError):
        CommercialStrategy(energy_range_wh=(150, 20))
    with pytest.raises(ValueError):
        CommercialStrategy(energy_range_wh=[150, 20])
    with pytest.raises(ValueError):
        CommercialStrategy(energy_range_wh=[20, 150, 200])
    with pytest.raises(ValueError):
        CommercialStrategy(energy_price=-1)
