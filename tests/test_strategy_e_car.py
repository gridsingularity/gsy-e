import pendulum
import pytest

from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market import Offer, Trade
from d3a.models.strategy.const import ARRIVAL_TIME, DEPART_TIME
from d3a.models.strategy.e_car import ECarStrategy


class FakeArea():
    def __init__(self, count):
        self.appliance = None
        self.name = 'FakeArea'
        self.count = count
        self.past_market = FakeMarket(0)
        # Setting "now" to "today" at 16hr
        #        time_in_hour = Interval(minutes=0, seconds=0)
        #        self.now = now.at(hour=16, minute=0, second=0).add_timedelta(
        #            (time_in_hour // self.config.slot_length) * self.config.slot_length
        #        )
        dt = pendulum.now()
        times = [dt.at(ARRIVAL_TIME, 0, 0, 0), dt.at(DEPART_TIME, 0, 0, 0)]
        self.now = times[count]

    @property
    def config(self):
        return DEFAULT_CONFIG

    @property
    def markets(self):
        return {"Fake Market": FakeMarket(self.count)}

    @property
    def cheapest_offers(self):
        offers = [
            [Offer('id', 12, 0.4, 'A', self)],
            [Offer('id', 12, 0.4, 'A', self)],
            [Offer('id', 20, 1, 'A', self)],
            [Offer('id', 20, 5.1, 'A', self)],
            [Offer('id', 20, 5.1, 'A', market=self.current_market)]
        ]
        return offers[self.count]

    @property
    def past_markets(self):
        return {"past market": self.past_market}


class FakeMarket:
    def __init__(self, count):
        self.count = count
        self.trade = Trade('id', 'time', Offer('id', 11.8, 0.5, 'A', self),
                           'FakeArea', 'buyer'
                           )
        self.created_offers = []

    @property
    def offers(self):
        return {'id': Offer('id', 100, 1, 'A', market=FakeMarket(0))}

    @property
    def sorted_offers(self):
        offers = [
            [Offer('id', 11.8, 0.5, 'A', self)],
            [Offer('id', 20, 0.5, 'A', self)],
            [Offer('id', 20, 1, 'A', self)],
            [Offer('id', 19, 5.1, 'A', self)]
        ]
        return offers[self.count]

    def offer(self, price, energy, seller, market=None):
        offer = Offer('id', price, energy, seller, market)
        self.created_offers.append(offer)
        return offer

    def delete_offer(self, id):
        return id


"""TEST1"""


# Test if car arrives correctly

@pytest.fixture()
def area_test1():
    return FakeArea(0)


@pytest.fixture()
def e_car_strategy_test1(area_test1, called):
    e = ECarStrategy()
    e.owner = area_test1
    e.area = area_test1
    e.arrive = called
    e.arrival_times_not_reached = list(range(23))
    e.arrival_times_not_reached.remove(ARRIVAL_TIME)
    return e


def test_car_arrival(e_car_strategy_test1, area_test1):
    e_car_strategy_test1.arrival_time = ARRIVAL_TIME
    e_car_strategy_test1.event_tick(area=area_test1)
    assert len(e_car_strategy_test1.arrive.calls) == 1


def test_car_not_arrived(e_car_strategy_test1, area_test1):
    for i in e_car_strategy_test1.arrival_times_not_reached:
        e_car_strategy_test1.arrival_time = i
        e_car_strategy_test1.event_tick(area=area_test1)
        assert len(e_car_strategy_test1.arrive.calls) == 0


"""TEST2"""


# Test if car departs correctly

@pytest.fixture()
def area_test2():
    return FakeArea(1)


@pytest.fixture()
def e_car_strategy_test2(area_test2, called):
    e = ECarStrategy()
    e.owner = area_test2
    e.area = area_test2
    e.depart = called
    e.depart_times_not_reached = list(range(24))
    e.depart_times_not_reached.remove(DEPART_TIME)
    e.depart_times_not_reached.remove(ARRIVAL_TIME)
    return e


def test_car_depart(e_car_strategy_test2, area_test2):
    e_car_strategy_test2.depart_time = DEPART_TIME
    e_car_strategy_test2.event_tick(area=area_test2)
    assert len(e_car_strategy_test2.depart.calls) == 1


def test_car_not_depart(e_car_strategy_test2, area_test2):
    for i in e_car_strategy_test2.depart_times_not_reached:
        e_car_strategy_test2.depart_time = i
        e_car_strategy_test2.event_tick(area=area_test2)
        assert len(e_car_strategy_test2.depart.calls) == 0


"""TEST3"""


# Check if battery unloads

def test_ecar_unload(e_car_strategy_test1, area_test1):
    e_car_strategy_test1.connected_to_grid = False
    e_car_strategy_test1.used_storage = 66
    e_car_strategy_test1.event_tick(area=area_test1)
    assert e_car_strategy_test1.used_storage == 66 * 0.9999


"""TEST4"""


# Check if arrival is handled correctly

@pytest.fixture()
def e_car_strategy_test4(area_test1, called):
    e = ECarStrategy()
    e.owner = area_test1
    e.area = area_test1
    e.sell_energy = called
    return e


def test_ecar_arrical(e_car_strategy_test4):
    e_car_strategy_test4.arrive()
    assert e_car_strategy_test4.connected_to_grid
    assert len(e_car_strategy_test4.sell_energy.calls) == 1


"""TEST5"""


# Check if departure is handled correctly

@pytest.fixture()
def e_car_strategy_test5(area_test1, called):
    e = ECarStrategy()
    e.owner = area_test1
    e.area = area_test1
    e.sell_energy = called
    e.offers.post(Offer('id', 1, 1, 'A', market=area_test1.past_market), area_test1.past_market)
    return e


def test_ecar_departure(e_car_strategy_test5):
    e_car_strategy_test5.depart()
    assert not e_car_strategy_test5.connected_to_grid
    assert e_car_strategy_test5.used_storage == 1


"""TEST6"""


# Check if market cycle is executed correctly

@pytest.fixture()
def e_car_strategy_test6(area_test1, called):
    e = ECarStrategy()
    e.owner = area_test1
    e.area = area_test1
    e.connected_to_grid = True
    e.event_market_cycle = called
    return e


def test_ecar_market_cycle(e_car_strategy_test6, area_test1):
    e_car_strategy_test6.event_market_cycle()
    assert len(e_car_strategy_test6.event_market_cycle.calls) == 1
