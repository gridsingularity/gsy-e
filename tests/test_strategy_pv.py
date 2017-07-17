import pytest
import pendulum
from pendulum import Pendulum

from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market import Offer, Trade
from d3a.models.strategy.pv import PVStrategy

ENERGY_FORECAST = {}  # type: Dict[Time, float]
TIME = pendulum.today().at(hour=10, minute=45, second=2)


class FakeArea():
    def __init__(self, count):
        self.current_tick = 2
        self.appliance = None
        self.name = 'FakeArea'
        self.count = count
        self.test_market = FakeMarket(0)

    @property
    def config(self):
        return DEFAULT_CONFIG

    @property
    def now(self) -> Pendulum:
        """
        Return the 'current time' as a `Pendulum` object.
        Can be overridden in subclasses to change the meaning of 'now'.

        In this default implementation 'current time' is defined by the number of ticks that
        have passed.
        """
        return Pendulum.now().start_of('day').add_timedelta(
            self.config.tick_length * self.current_tick
        )

    @property
    def historical_avg_price(self):
        return 30

    @property
    def markets(self):
        return {TIME: self.test_market}


class FakeMarket:
    def __init__(self, count):
        self.count = count
        self.created_offers = []
        self.offers = {'id': Offer(id='id', price=10, energy=0.5, seller='A', market=self)}

    def offer(self, price, energy, seller, market=None):
        offer = Offer('id', price, energy, seller, market)
        self.created_offers.append(offer)
        offer.id = 'id'
        return offer

    def delete_offer(self, offer_id):
        return


"""TEST1"""


@pytest.fixture()
def area_test1():
    return FakeArea(0)


@pytest.fixture()
def pv_test1(area_test1):
    p = PVStrategy()
    p.area = area_test1
    p.owner = area_test1
    return p


def testing_activation(pv_test1, area_test1):
    pv_test1.event_activate()
    # Pendulum.today() returns pendulum object with the date of today and midnight
    assert pv_test1.midnight == pendulum.today()
    global ENERGY_FORECAST
    ENERGY_FORECAST = pv_test1.energy_production_forecast


"""TEST2"""


@pytest.fixture()
def area_test2():
    return FakeArea(0)


@pytest.fixture()
def market_test2(area_test2):
    return area_test2.test_market


@pytest.fixture()
def pv_test2(area_test2, called):
    p = PVStrategy()
    p.area = area_test2
    p.owner = area_test2
    p.offers_posted = {}
    p.energy_production_forecast = ENERGY_FORECAST
    p.decrease_offer_price = called
    return p


def testing_event_tick(pv_test2, market_test2, area_test2):
    pv_test2.event_activate()
    pv_test2.event_tick(area=area_test2)
    assert len(market_test2.created_offers) == 1
    assert market_test2.created_offers[0].price == 29.9 * pv_test2.energy_production_forecast[TIME]
    assert pv_test2.energy_production_forecast[
               pendulum.today().at(hour=0, minute=0, second=2)
           ] == 0
    area_test2.current_tick = DEFAULT_CONFIG.ticks_per_slot - 2
    pv_test2.event_tick(area=area_test2)
    assert len(pv_test2.decrease_offer_price.calls) == 1


"""TEST 3"""


@pytest.fixture()
def area_test3():
    return FakeArea(0)


@pytest.fixture()
def market_test3(area_test3):
    return area_test3.test_market


@pytest.fixture()
def pv_test3(area_test3, called):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    p.offers_posted = {'id': area_test3.test_market}
    return p


def testing_decrease_offer_price(area_test3, market_test3, pv_test3):
    pv_test3.decrease_offer_price(area_test3.test_market)
    for offer, market in pv_test3.offers_posted:
        if market == area_test3.test_market:
            assert offer.price == market_test3.offers['id'].price * 0.


"""TEST 4"""


@pytest.fixture()
def pv_test4(area_test3, called):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    p.offers_posted = {'id': area_test3.test_market}
    return p


def testing_event_trade(area_test3, pv_test4):
    pv_test4.event_trade(market=area_test3.test_market,
                         trade=Trade(id='id', time='time',
                                     offer=Offer(id='id', price=20, energy=1, seller='FakeArea'),
                                     seller=area_test3, buyer='buyer'
                                     )
                         )
    assert len(pv_test4.offers_posted) == 0


"""TEST 5"""


@pytest.fixture()
def pv_test5(area_test3, called):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    p.offers_posted = {'id': area_test3.test_market}
    return p


def testing_trigger_risk(pv_test5):
    pv_test5.trigger_risk(99)
    assert pv_test5.risk == 99
    with pytest.raises(ValueError):
        pv_test5.trigger_risk(101)
    with pytest.raises(ValueError):
        pv_test5.trigger_risk(-1)
