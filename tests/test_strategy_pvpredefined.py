import pytest
import pendulum
import uuid
from pendulum import DateTime, duration

from d3a import TIME_ZONE
from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market import Offer, Trade
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy
from d3a.models.strategy.const import ConstSettings


ENERGY_FORECAST = {}  # type: Dict[Time, float]
TIME = pendulum.today(tz=TIME_ZONE).at(hour=10, minute=45, second=2)


class FakeArea():
    def __init__(self, count):
        self.current_tick = 2
        self.appliance = None
        self.name = 'FakeArea'
        self.count = count
        self.test_market = FakeMarket(0)

    def get_future_market_from_id(self, id):
        return self.test_market

    @property
    def config(self):
        return DEFAULT_CONFIG

    @property
    def now(self) -> DateTime:
        """
        Return the 'current time' as a `DateTime` object.
        Can be overridden in subclasses to change the meaning of 'now'.

        In this default implementation 'current time' is defined by the number of ticks that
        have passed.
        """
        return DateTime.now(tz=TIME_ZONE).start_of('day') + (
            self.config.tick_length * self.current_tick
        )

    @property
    def historical_avg_rate(self):
        return 30

    @property
    def all_markets(self):
        return [self.test_market]


class FakeMarket:
    def __init__(self, count):
        self.count = count
        self.id = count
        self.created_offers = []
        self.offers = {'id': Offer(id='id', price=10, energy=0.5, seller='A', market=self)}

    def offer(self, price, energy, seller, market=None):
        offer = Offer(str(uuid.uuid4()), price, energy, seller, market)
        self.created_offers.append(offer)
        self.offers[offer.id] = offer
        return offer

    @property
    def time_slot(self):
        return TIME

    @property
    def time_slot_str(self):
        return self.time_slot.strftime("%H:%M")

    def delete_offer(self, offer_id):
        return


class FakeTrade:
    def __init__(self, offer):
        self.offer = offer

    @property
    def buyer(self):
        return "FakeBuyer"


"""TEST1"""


@pytest.fixture()
def area_test1():
    return FakeArea(0)


@pytest.fixture()
def pv_test1(area_test1):
    p = PVPredefinedStrategy(cloud_coverage=ConstSettings.PVSettings.DEFAULT_POWER_PROFILE)
    p.area = area_test1
    p.owner = area_test1
    return p


def test_activation(pv_test1, area_test1):
    pv_test1.event_activate()
    assert pv_test1._decrease_price_every_nr_s > 0
    global ENERGY_FORECAST
    ENERGY_FORECAST = pv_test1.energy_production_forecast_kWh


"""TEST 3"""


@pytest.fixture()
def area_test3():
    return FakeArea(0)


@pytest.fixture()
def market_test3(area_test3):
    return area_test3.test_market


@pytest.fixture()
def pv_test3(area_test3):
    p = PVPredefinedStrategy(cloud_coverage=ConstSettings.PVSettings.DEFAULT_POWER_PROFILE)
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {Offer('id', 1, 1, 'FakeArea', market=area_test3.test_market):
                       area_test3.test_market}
    return p


def testing_decrease_offer_price(area_test3, market_test3, pv_test3):
    assert len(pv_test3.offers.posted.items()) == 1
    pv_test3.event_activate()
    pv_test3.event_market_cycle()
    old_offer = list(pv_test3.offers.posted.keys())[0]
    pv_test3._decrease_offer_price(area_test3.test_market,
                                   pv_test3._calculate_price_decrease_rate(
                                           area_test3.test_market))
    new_offer = list(pv_test3.offers.posted.keys())[0]
    assert new_offer.price < old_offer.price


"""TEST 4"""


@pytest.fixture()
def pv_test4(area_test3, called):
    p = PVPredefinedStrategy(cloud_coverage=ConstSettings.PVSettings.DEFAULT_POWER_PROFILE)
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {
        Offer(id='id', price=20, energy=1, seller='FakeArea'): area_test3.test_market
    }
    return p


def testing_event_trade(area_test3, pv_test4):
    pv_test4.event_trade(market_id=area_test3.test_market.id,
                         trade=Trade(id='id', time='time',
                                     offer=Offer(id='id', price=20, energy=1, seller='FakeArea'),
                                     seller=area_test3, buyer='buyer'
                                     )
                         )
    assert len(pv_test4.offers.open) == 0


"""TEST 5"""


@pytest.fixture()
def pv_test5(area_test3, called):
    p = PVPredefinedStrategy(cloud_coverage=0)
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {'id': area_test3.test_market}
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
    p = PVPredefinedStrategy(cloud_coverage=ConstSettings.PVSettings.DEFAULT_POWER_PROFILE)
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {}
    return p


def testing_produced_energy_forecast_real_data(pv_test6):

    pv_test6.event_activate()
    morning_time = pendulum.today(tz=TIME_ZONE).at(hour=5, minute=10, second=0)
    afternoon_time = pendulum.today(tz=TIME_ZONE).at(hour=19, minute=10, second=0)

    class Counts(object):
        def __init__(self, time):
            self.total = 0
            self.count = 0
            self.time = time
    morning_counts = Counts('morning')
    afternoon_counts = Counts('afternoon')
    evening_counts = Counts('evening')
    for (time, power) in pv_test6.energy_production_forecast_kWh.items():
        if time < morning_time:
            morning_counts.total += 1
            morning_counts.count = morning_counts.count + 1 \
                if pv_test6.energy_production_forecast_kWh[time] == 0 else morning_counts.count
        elif morning_time < time < afternoon_time:
            afternoon_counts.total += 1
            afternoon_counts.count = afternoon_counts.count + 1 \
                if pv_test6.energy_production_forecast_kWh[time] > 0.001 \
                else afternoon_counts.count
        elif time > afternoon_time:
            evening_counts.total += 1
            evening_counts.count = evening_counts.count + 1 \
                if pv_test6.energy_production_forecast_kWh[time] == 0 else evening_counts.count

    total_count = morning_counts.total + afternoon_counts.total + evening_counts.total
    assert len(list(pv_test6.energy_production_forecast_kWh.items())) == total_count

    morning_count_percent = (morning_counts.count / morning_counts.total) * 100
    assert morning_count_percent > 90

    afternoon_count_percent = (afternoon_counts.count / afternoon_counts.total) * 100
    assert afternoon_count_percent > 90

    evening_count_percent = (evening_counts.count / evening_counts.total) * 100
    assert evening_count_percent > 90


# The pv sells its whole production at once if possible.
# Make sure that it doesnt offer it again after selling.
def test_does_not_offer_sold_energy_again(pv_test6, market_test3):
    pv_test6.event_activate()
    pv_test6.event_market_cycle()
    assert market_test3.created_offers[0].energy == pv_test6.energy_production_forecast_kWh[TIME]
    fake_trade = FakeTrade(market_test3.created_offers[0])
    pv_test6.event_trade(market_id=market_test3.id, trade=fake_trade)
    market_test3.created_offers = []
    pv_test6.event_tick(area=area_test3)
    assert not market_test3.created_offers


""" TEST 7"""
# Testing with different energy_profiles


@pytest.fixture()
def area_test7():
    return FakeArea(0)


@pytest.fixture()
def pv_test_sunny(area_test3):
    p = PVPredefinedStrategy(cloud_coverage=0)
    p.area = area_test3
    p.owner = area_test3
    return p


@pytest.fixture()
def pv_test_partial(area_test7):
    p = PVPredefinedStrategy(cloud_coverage=2)
    p.area = area_test7
    p.owner = area_test7
    return p


@pytest.fixture()
def pv_test_cloudy(area_test7):
    p = PVPredefinedStrategy(cloud_coverage=1)
    p.area = area_test7
    p.owner = area_test7
    p.area.config.slot_length = duration(minutes=20)
    return p


def test_power_profiles(pv_test_sunny, pv_test_partial, pv_test_cloudy):

    pv_test_sunny.event_activate()
    pv_test_partial.event_activate()
    pv_test_cloudy.event_activate()

    assert sum(pv_test_sunny.energy_production_forecast_kWh.values()) > 0
    assert sum(pv_test_partial.energy_production_forecast_kWh.values()) > 0
    assert sum(pv_test_cloudy.energy_production_forecast_kWh.values()) > 0

    # checking whether the interpolation is done on the right sampling points
    assert list(pv_test_cloudy.energy_production_forecast_kWh.keys())[1].minute % \
        pv_test_partial.area.config.slot_length.minutes == 0
