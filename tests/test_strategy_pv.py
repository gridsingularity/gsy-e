import pytest
import pendulum
import uuid
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
        offer = Offer(str(uuid.uuid4()), price, energy, seller, market)
        self.created_offers.append(offer)
        self.offers[offer.id] = offer
        return offer

    def delete_offer(self, offer_id):
        return


class FakeTrade:
    def __init__(self, offer):
        self.offer = offer


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
def pv_test2(area_test2):
    p = PVStrategy()
    p.area = area_test2
    p.owner = area_test2
    p.offers_posted = {}
    p.energy_production_forecast = ENERGY_FORECAST
    return p


def testing_event_tick(pv_test2, market_test2, area_test2):
    pv_test2.event_activate()
    pv_test2.event_tick(area=area_test2)
    assert len(market_test2.created_offers) == 1
    assert len(pv_test2.offers_posted.items()) == 1
    offer_id1 = list(pv_test2.offers_posted.keys())[0]
    offer1 = market_test2.offers[offer_id1]
    assert market_test2.created_offers[0].price == 29.9 * pv_test2.energy_production_forecast[TIME]
    assert pv_test2.energy_production_forecast[
               pendulum.today().at(hour=0, minute=0, second=2)
           ] == 0
    area_test2.current_tick = DEFAULT_CONFIG.ticks_per_slot - 2
    pv_test2.event_tick(area=area_test2)
    offer_id2 = list(pv_test2.offers_posted.keys())[0]
    offer2 = market_test2.offers[offer_id2]
    assert offer1 != offer2
    assert len(pv_test2.offers_posted.items()) == 1
    # assert len(pv_test2.decrease_offer_price.calls) == 1


"""TEST 3"""


@pytest.fixture()
def area_test3():
    return FakeArea(0)


@pytest.fixture()
def market_test3(area_test3):
    return area_test3.test_market


@pytest.fixture()
def pv_test3(area_test3):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    p.offers_posted = {'id': area_test3.test_market}
    return p


def testing_decrease_offer_price(area_test3, market_test3, pv_test3):
    assert len(pv_test3.offers_posted.items()) == 1
    old_offer = market_test3.offers['id']
    pv_test3.decrease_offer_price(area_test3.test_market)
    new_offer_id = list(pv_test3.offers_posted.keys())[0]
    new_offer = market_test3.offers[new_offer_id]
    assert new_offer.price < old_offer.price


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


""" TEST 6"""
# Testing with different risk test parameters


@pytest.fixture()
def pv_test6(area_test3):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    p.offers_posted = {}
    p.energy_production_forecast = ENERGY_FORECAST
    return p


def testing_low_risk(pv_test6, market_test3):
    pv_test6.risk = 20
    pv_test6.event_activate()
    pv_test6.event_tick(area=area_test3)
    assert market_test3.created_offers[0].price == \
        29.64 * pv_test6.energy_production_forecast[TIME]


# when risk < 50 rounded_energy_price < 29.9, risk > 50 rounded_energy_price = 29.9
def testing_high_risk(pv_test6, market_test3):
    pv_test6.risk = 90
    pv_test6.event_activate()
    pv_test6.event_tick(area=area_test3)
    assert market_test3.created_offers[0].price == \
        29.9 * pv_test6.energy_production_forecast[TIME]


def testing_produced_energy_forecast_real_data(pv_test6, market_test3):

    pv_test6.event_activate()
    morning_time = pendulum.today().at(hour=8, minute=20, second=0)
    afternoon_time = pendulum.today().at(hour=16, minute=40, second=0)

    class Counts(object):
        def __init__(self, time):
            self.total = 0
            self.count = 0
            self.time = time
    morning_counts = Counts('morning')
    afternoon_counts = Counts('afternoon')
    evening_counts = Counts('evening')
    for (time, power) in pv_test6.energy_production_forecast.items():
        if time < morning_time:
            morning_counts.total += 1
            morning_counts.count = morning_counts.count + 1 \
                if pv_test6.energy_production_forecast[time] == 0 else morning_counts.count
        elif morning_time < time < afternoon_time:
            afternoon_counts.total += 1
            afternoon_counts.count = afternoon_counts.count + 1 \
                if pv_test6.energy_production_forecast[time] > 0.1 else afternoon_counts.count
        elif time > afternoon_time:
            evening_counts.total += 1
            evening_counts.count = evening_counts.count + 1 \
                if pv_test6.energy_production_forecast[time] == 0 else evening_counts.count

    total_count = morning_counts.total + afternoon_counts.total + evening_counts.total
    assert len(list(pv_test6.energy_production_forecast.items())) == total_count

    # Morning power generation is less we check this by percentage wise counts in the morning

    morning_count_percent = (morning_counts.count / morning_counts.total) * 100
    assert morning_count_percent > 90

    # Afternoon power generation should be subsequently larger

    afternoon_count_percent = (afternoon_counts.count / afternoon_counts.total) * 100
    assert afternoon_count_percent > 50

    # Evening power generation should again drop to low levels

    evening_count_percent = (evening_counts.count / evening_counts.total) * 100
    assert evening_count_percent > 90


# The pv sells its whole production at once if possible.
# Make sure that it doesnt offer it again after selling.

@pytest.mark.skip('bug waiting to be fixed')
def test_does_not_offer_sold_energy_again(pv_test6, market_test3):
    pv_test6.event_activate()
    pv_test6.event_tick(area=area_test3)
    assert market_test3.created_offers[0].energy == pv_test6.energy_production_forecast[TIME]
    fake_trade = FakeTrade(market_test3.created_offers[0])
    pv_test6.event_trade(market=market_test3, trade=fake_trade)
    market_test3.created_offers = []
    pv_test6.event_tick(area=area_test3)
    assert not market_test3.created_offers
