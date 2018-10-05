import pytest
import sys

from d3a.models.market import Offer, Trade, BalancingOffer
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.area import DEFAULT_CONFIG
from d3a.device_registry import DeviceRegistry


class FakeArea:
    def __init__(self, count):
        self.current_tick = 2
        self.appliance = None
        self.name = 'FakeArea'
        self.test_market = FakeMarket(0)
        self.test_balancing_market = FakeMarket(1)
        self.test_balancing_market_2 = FakeMarket(2)

    @property
    def markets(self):
        return {"now": self.test_market}

    @property
    def balancing_markets(self):
        return {"now": self.test_balancing_market, "now+1": self.test_balancing_market_2}

    @property
    def config(self):
        return DEFAULT_CONFIG


class FakeMarket:
    def __init__(self, count):
        self.count = count
        self.created_offers = []
        self.created_balancing_offers = []

    def offer(self, price, energy, seller, market=None):
        offer = Offer('id', price, energy, seller, market)
        self.created_offers.append(offer)
        offer.id = 'id'
        return offer

    def balancing_offer(self, price, energy, seller, market=None):
        offer = BalancingOffer('id', price, energy, seller, market)
        self.created_balancing_offers.append(offer)
        offer.id = 'id'
        return offer


"""TEST1"""


@pytest.fixture()
def area_test1():
    return FakeArea(0)


@pytest.fixture()
def commercial_test1(area_test1):
    c = CommercialStrategy(energy_rate=30)
    c.area = area_test1
    c.owner = area_test1
    return c


def testing_event_activate(commercial_test1, area_test1):
    commercial_test1.event_activate()
    assert len(area_test1.test_market.created_offers) == 1
    assert area_test1.test_market.created_offers[0].energy == sys.maxsize


def test_balancing_offers_are_not_sent_to_all_markets_if_device_not_in_registry(
        commercial_test1, area_test1):
    DeviceRegistry.REGISTRY = {}
    commercial_test1.event_activate()
    assert len(area_test1.test_balancing_market.created_balancing_offers) == 0


def test_balancing_offers_are_sent_to_all_markets_if_device_in_registry(
        commercial_test1, area_test1):
    DeviceRegistry.REGISTRY = {'FakeArea': (30, 40)}
    commercial_test1.event_activate()
    assert len(area_test1.test_balancing_market.created_balancing_offers) == 1
    assert area_test1.test_balancing_market.created_balancing_offers[0].energy == sys.maxsize
    assert area_test1.test_balancing_market.created_balancing_offers[0].price == sys.maxsize * 40
    assert len(area_test1.test_balancing_market_2.created_balancing_offers) == 1
    assert area_test1.test_balancing_market_2.created_balancing_offers[0].energy == sys.maxsize
    assert area_test1.test_balancing_market_2.created_balancing_offers[0].price == sys.maxsize * 40

    DeviceRegistry.REGISTRY = {}


def test_event_market_cycle_does_not_create_balancing_offer_if_not_in_registry(
        commercial_test1, area_test1):
    DeviceRegistry.REGISTRY = {}
    commercial_test1.event_activate()
    commercial_test1.event_market_cycle()
    assert len(area_test1.test_balancing_market.created_balancing_offers) == 0
    assert len(area_test1.test_balancing_market_2.created_balancing_offers) == 0


def test_event_market_cycle_creates_balancing_offer_on_last_market_if_in_registry(
        commercial_test1, area_test1):
    DeviceRegistry.REGISTRY = {"FakeArea": (40, 50)}
    commercial_test1.event_market_cycle()
    assert len(area_test1.test_balancing_market.created_balancing_offers) == 0
    assert len(area_test1.test_balancing_market_2.created_balancing_offers) == 1
    assert area_test1.test_balancing_market_2.created_balancing_offers[0].energy == \
        sys.maxsize
    assert area_test1.test_balancing_market_2.created_balancing_offers[0].price == \
        sys.maxsize * 50

    DeviceRegistry.REGISTRY = {}


"""TEST2"""


@pytest.fixture()
def area_test2():
    return FakeArea(0)


@pytest.fixture()
def commercial_test2(area_test2):
    c = CommercialStrategy(energy_rate=30)
    c.area = area_test2
    c.owner = area_test2
    return c


def test_event_trade(area_test2, commercial_test2):
    commercial_test2.event_activate()
    traded_offer = Offer(id='id', price=20, energy=1, seller='FakeArea',)
    commercial_test2.event_trade(market=area_test2.test_market,
                                 trade=Trade(id='id',
                                             time='time',
                                             offer=traded_offer,
                                             seller='FakeArea',
                                             buyer='buyer'
                                             )
                                 )
    assert len(area_test2.test_market.created_offers) == 1
    assert area_test2.test_market.created_offers[-1].energy == sys.maxsize


def test_on_offer_changed(area_test2, commercial_test2):
    commercial_test2.event_activate()
    existing_offer = Offer(id='id', price=20, energy=1, seller='FakeArea')
    new_offer = Offer(id='new_id', price=15, energy=0.75, seller='FakeArea')
    commercial_test2.event_offer_changed(market=area_test2.test_market,
                                         existing_offer=existing_offer,
                                         new_offer=new_offer)
    assert existing_offer.id in commercial_test2.offers.changed
    assert commercial_test2.offers.changed[existing_offer.id] == new_offer


def test_event_trade_after_offer_changed_partial_offer(area_test2, commercial_test2):
    existing_offer = Offer(id='old_id', price=20, energy=1, seller='FakeArea')
    new_offer = Offer(id='new_id', price=15, energy=0.75, seller='FakeArea')

    commercial_test2.offers.post(existing_offer, area_test2.test_market)
    commercial_test2.offers.post(new_offer, area_test2.test_market)
    commercial_test2.event_offer_changed(market=area_test2.test_market,
                                         existing_offer=existing_offer,
                                         new_offer=new_offer)
    assert existing_offer.id in commercial_test2.offers.changed
    assert commercial_test2.offers.changed[existing_offer.id] == new_offer
    commercial_test2.event_trade(market=area_test2.test_market,
                                 trade=Trade(id='id',
                                             time='time',
                                             offer=existing_offer,
                                             seller='FakeArea',
                                             buyer='buyer')
                                 )

    assert len(commercial_test2.offers.posted) == 2
    assert new_offer in commercial_test2.offers.posted
    assert commercial_test2.offers.posted[new_offer] == area_test2.test_market
    assert len(commercial_test2.offers.changed) == 0
    assert len(commercial_test2.offers.sold) == 1
    assert existing_offer.id in commercial_test2.offers.sold[area_test2.test_market]


def test_validate_posted_offers_get_updated_on_offer_energy_method(area_test2, commercial_test2):
    commercial_test2.offer_energy(area_test2.test_market)
    assert len(commercial_test2.offers.posted) == 1
    assert list(commercial_test2.offers.posted.values())[0] == area_test2.test_market


"""TEST3"""


@pytest.fixture()
def area_test3():
    return FakeArea(0)


@pytest.fixture()
def commercial_test3(area_test3):
    c = CommercialStrategy(energy_rate=30)
    c.area = area_test3
    c.owner = area_test3
    return c


def testing_event_market_cycle(commercial_test3, area_test3):
    commercial_test3.event_activate()
    commercial_test3.event_market_cycle()
    assert len(area_test3.test_market.created_offers) == 2
    assert area_test3.test_market.created_offers[-1].energy == sys.maxsize


def test_commercial_producer_constructor_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        CommercialStrategy(energy_rate=-1)
