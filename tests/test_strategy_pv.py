import pytest
import pendulum
import uuid
from pendulum import DateTime

from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market import Offer, Trade
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.const import ConstSettings
from d3a import TIME_FORMAT

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
    def now(self) -> DateTime:
        """
        Return the 'current time' as a `DateTime` object.
        Can be overridden in subclasses to change the meaning of 'now'.

        In this default implementation 'current time' is defined by the number of ticks that
        have passed.
        """
        return DateTime.now().start_of('day') + (
            self.config.tick_length * self.current_tick
        )

    @property
    def historical_avg_rate(self):
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

    @property
    def time_slot(self):
        return DateTime.now().start_of('day')

    @property
    def time_slot_str(self):
        return self.time_slot.strftime(TIME_FORMAT)

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
    p = PVStrategy()
    p.area = area_test1
    p.owner = area_test1
    return p


def testing_activation(pv_test1, area_test1):
    pv_test1.event_activate()
    # DateTime.today() returns pendulum object with the date of today and midnight
    assert pv_test1.midnight == pendulum.today()
    global ENERGY_FORECAST
    ENERGY_FORECAST = pv_test1.energy_production_forecast_kWh


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
    p.offers.posted = {}
    p.energy_production_forecast_kWh = ENERGY_FORECAST
    return p


@pytest.mark.skip('broken as event_tick does not decrease offer price with every tick')
def testing_event_tick(pv_test2, market_test2, area_test2):
    pv_test2.event_activate()
    pv_test2.event_tick(area=area_test2)
    assert len(market_test2.created_offers) == 1
    assert len(pv_test2.offers.posted.items()) == 1
    offer_id1 = list(pv_test2.offers.posted.keys())[0]
    offer1 = market_test2.offers[offer_id1]
    assert market_test2.created_offers[0].price == \
        29.9 * pv_test2.energy_production_forecast_kWh[TIME]
    assert pv_test2.energy_production_forecast_kWh[
               pendulum.today().at(hour=0, minute=0, second=2)
           ] == 0
    area_test2.current_tick = DEFAULT_CONFIG.ticks_per_slot - 2
    pv_test2.event_tick(area=area_test2)
    offer_id2 = list(pv_test2.offers.posted.keys())[0]
    offer2 = market_test2.offers[offer_id2]
    assert offer1 != offer2
    assert len(pv_test2.offers.posted.items()) == 1
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
    p.offers.posted = {Offer('id', 1, 1, 'FakeArea', market=area_test3.test_market):
                       area_test3.test_market}
    return p


def testing_decrease_offer_price(area_test3, pv_test3):
    assert len(pv_test3.offers.posted.items()) == 1
    pv_test3.event_activate()
    pv_test3.event_market_cycle()
    for i in range(3):
        old_offer = list(pv_test3.offers.posted.keys())[0]
        pv_test3._decrease_offer_price(area_test3.test_market,
                                       pv_test3._calculate_price_decrease_rate(
                                           area_test3.test_market))
        new_offer = list(pv_test3.offers.posted.keys())[0]
        assert new_offer.price < old_offer.price


def test_same_slot_price_drop_does_not_reduce_price_below_threshold(area_test3, pv_test3):
    pv_test3.event_activate()
    pv_test3.event_market_cycle()
    for _ in range(100):
        pv_test3._decrease_offer_price(area_test3.test_market,
                                       pv_test3._calculate_price_decrease_rate(
                                           area_test3.test_market))
    new_offer = list(pv_test3.offers.posted.keys())[-1]
    assert new_offer.price / new_offer.energy >= ConstSettings.MIN_PV_SELLING_RATE


"""TEST 4"""


@pytest.fixture()
def pv_test4(area_test3, called):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {
        Offer(id='id', price=20, energy=1, seller='FakeArea'): area_test3.test_market
    }
    return p


def testing_event_trade(area_test3, pv_test4):
    pv_test4.event_trade(market=area_test3.test_market,
                         trade=Trade(id='id', time='time',
                                     offer=Offer(id='id', price=20, energy=1, seller='FakeArea'),
                                     seller=area_test3, buyer='buyer'
                                     )
                         )
    assert len(pv_test4.offers.open) == 0


"""TEST 5"""


@pytest.fixture()
def pv_test5(area_test3, called):
    p = PVStrategy()
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
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {}
    p.energy_production_forecast_kWh = ENERGY_FORECAST
    return p


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

def test_does_not_offer_sold_energy_again(pv_test6, market_test3):
    pv_test6.event_activate()
    pv_test6.event_market_cycle()
    assert market_test3.created_offers[0].energy == pv_test6.energy_production_forecast_kWh[TIME]
    fake_trade = FakeTrade(market_test3.created_offers[0])
    pv_test6.event_trade(market=market_test3, trade=fake_trade)
    market_test3.created_offers = []
    pv_test6.event_tick(area=area_test3)
    assert not market_test3.created_offers


def test_pv_constructor_rejects_incorrect_parameters():
    with pytest.raises(ValueError):
        PVStrategy(risk=-1)
    with pytest.raises(ValueError):
        PVStrategy(risk=101)
    with pytest.raises(ValueError):
        PVStrategy(panel_count=0)


"""TEST7"""


@pytest.fixture()
def pv_test7(area_test3):
    p = PVStrategy(1, 95)
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {Offer('id', 1, 1, 'FakeArea', market=area_test3.test_market):
                       area_test3.test_market}
    return p


def testing_low_risk(area_test3, pv_test7):
    assert len(pv_test7.offers.posted.items()) == 1
    pv_test7.event_activate()
    pv_test7.event_market_cycle()
    for i in range(3):
        old_offer = list(pv_test7.offers.posted.keys())[0]
        pv_test7._decrease_offer_price(area_test3.test_market,
                                       pv_test7._calculate_price_decrease_rate(
                                           area_test3.test_market))
        new_offer = list(pv_test7.offers.posted.keys())[0]
        price_dec_per_slot = (area_test3.historical_avg_rate) * (1 - pv_test7.risk
                                                                 / ConstSettings.MAX_RISK)
        price_updates_per_slot = int(area_test3.config.slot_length.seconds
                                     / pv_test7._decrease_price_every_nr_s.m)
        price_dec_per_update = price_dec_per_slot / price_updates_per_slot
        assert new_offer.price == old_offer.price - (old_offer.energy * price_dec_per_update)


"""TEST8"""


@pytest.fixture()
def pv_test8(area_test3):
    p = PVStrategy(1, 10)
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {Offer('id', 1, 1, 'FakeArea', market=area_test3.test_market):
                       area_test3.test_market}
    return p


def testing_high_risk(area_test3, pv_test8):
    assert len(pv_test8.offers.posted.items()) == 1
    pv_test8.event_activate()
    pv_test8.event_market_cycle()
    for i in range(3):
        old_offer = list(pv_test8.offers.posted.keys())[0]
        pv_test8._decrease_offer_price(area_test3.test_market,
                                       pv_test8._calculate_price_decrease_rate(
                                           area_test3.test_market))
        new_offer = list(pv_test8.offers.posted.keys())[0]
        price_dec_per_slot = (area_test3.historical_avg_rate) * (1 - pv_test8.risk /
                                                                 ConstSettings.MAX_RISK)
        price_updates_per_slot = int(area_test3.config.slot_length.seconds
                                     / pv_test8._decrease_price_every_nr_s.m)
        price_dec_per_update = price_dec_per_slot / price_updates_per_slot
        assert new_offer.price == old_offer.price - (old_offer.energy * price_dec_per_update)


"""TEST9"""


@pytest.fixture()
def area_test9():
    return FakeArea(0)


@pytest.fixture()
def market_test9(area_test9):
    return area_test9.test_market


@pytest.fixture()
def pv_test9(area_test9):
    p = PVStrategy(panel_count=3)
    p.area = area_test9
    p.owner = area_test9
    p.offers.posted = {}
    p.energy_production_forecast_kWh = ENERGY_FORECAST
    return p


def testing_number_of_pv_sell_offers(pv_test9, market_test9, area_test9):
    pv_test9.event_activate()
    pv_test9.event_market_cycle()
    assert len(market_test9.created_offers) == 1
