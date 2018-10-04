import pendulum
import pytest

from unittest.mock import Mock
from d3a import TIME_ZONE
from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market import Offer, Trade
from d3a.models.strategy.const import ConstSettings
from d3a.models.strategy.e_car import ECarStrategy


class FakeArea():
    def __init__(self, count):
        self.appliance = None
        self.name = 'FakeArea'
        self.count = count
        self.past_market = FakeMarket(0)
        # Setting "now" to "today" at 16hr
        #        time_in_hour = duration(minutes=0, seconds=0)
        #        self.now = now.at(hour=16, minute=0, second=0) + (
        #            (time_in_hour // self.config.slot_length) * self.config.slot_length
        #        )
        dt = pendulum.now(tz=TIME_ZONE)
        times = [dt.at(ConstSettings.ARRIVAL_TIME, 0, 0, 0),
                 dt.at(ConstSettings.DEPART_TIME, 0, 0, 0)]
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

    @property
    def current_market(self):
        return self.past_market


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
    e.arrival_times_not_reached.remove(ConstSettings.ARRIVAL_TIME)
    return e


def test_car_arrival(e_car_strategy_test1, area_test1):
    e_car_strategy_test1.arrival_time = ConstSettings.ARRIVAL_TIME
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
    e._remove_offers_on_depart = called
    e.buy_energy = lambda: None
    e.sell_energy = lambda: None
    e.depart_times_not_reached = list(range(24))
    e.depart_times_not_reached.remove(ConstSettings.DEPART_TIME)
    e.depart_times_not_reached.remove(ConstSettings.ARRIVAL_TIME)
    return e


def test_car_depart(e_car_strategy_test2, area_test2):
    e_car_strategy_test2.connected_to_grid = True
    e_car_strategy_test2.depart_time = ConstSettings.DEPART_TIME
    e_car_strategy_test2.event_tick(area=area_test2)
    assert len(e_car_strategy_test2._remove_offers_on_depart.calls) == 1
    assert not e_car_strategy_test2.connected_to_grid


def test_car_not_depart(e_car_strategy_test2, area_test2):
    e_car_strategy_test2.connected_to_grid = True
    for i in e_car_strategy_test2.depart_times_not_reached:
        e_car_strategy_test2.depart_time = i
        e_car_strategy_test2.event_tick(area=area_test2)
        assert len(e_car_strategy_test2._remove_offers_on_depart.calls) == 0
        assert e_car_strategy_test2.connected_to_grid


"""TEST3"""


# Check if battery unloads

def test_ecar_unload(e_car_strategy_test1, area_test1):
    e_car_strategy_test1.connected_to_grid = False
    e_car_strategy_test1.state._used_storage = 66
    e_car_strategy_test1.event_tick(area=area_test1)
    assert e_car_strategy_test1.state.used_storage == 66 * 0.9999


"""TEST4"""


# Check if arrival is handled correctly

@pytest.fixture()
def e_car_strategy_test4(area_test1, called):
    e = ECarStrategy()
    e.owner = area_test1
    e.area = area_test1
    e.sell_energy = Mock(return_value=None)
    e.buy_energy = lambda: None
    e.depart = called
    return e


def test_ecar_arrival(e_car_strategy_test4, area_test1):
    e_car_strategy_test4.arrive()
    assert e_car_strategy_test4.connected_to_grid
    assert e_car_strategy_test4.sell_energy.called
    for i in range(1000):
        e_car_strategy_test4.event_tick(area=area_test1)
        assert e_car_strategy_test4.connected_to_grid
        assert len(e_car_strategy_test4.depart.calls) == 0
        assert e_car_strategy_test4.sell_energy.call_count == i+2


"""TEST5"""


# Check if departure is handled correctly

@pytest.fixture()
def e_car_strategy_test5(area_test1, called):
    e = ECarStrategy()
    e.owner = area_test1
    e.area = area_test1
    e.sell_energy = called
    e.offers.post(Offer('id', 1, 1, 'A', market=area_test1.past_market), area_test1.past_market)
    e.state._offered_storage = 1
    return e


def test_ecar_departure(e_car_strategy_test5):
    e_car_strategy_test5.depart()
    assert not e_car_strategy_test5.connected_to_grid
    assert e_car_strategy_test5.state.used_storage == 1


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


def test_ecar_market_cycle(e_car_strategy_test6):
    e_car_strategy_test6.event_market_cycle()
    assert len(e_car_strategy_test6.event_market_cycle.calls) == 1


def test_ecar_constructor_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        ECarStrategy(arrival_time=-1)
    with pytest.raises(ValueError):
        ECarStrategy(arrival_time=24)
    with pytest.raises(ValueError):
        ECarStrategy(depart_time=-1)
    with pytest.raises(ValueError):
        ECarStrategy(depart_time=24)
    with pytest.raises(ValueError):
        ECarStrategy(arrival_time=12, depart_time=11)


def test_ecar_constructor_handles_none_arrive_depart_values():
    from d3a.models.strategy.const import ConstSettings
    try:
        ecar = ECarStrategy(arrival_time=None, depart_time=None)
        assert ecar.arrival_time == ConstSettings.ARRIVAL_TIME
        assert ecar.depart_time == ConstSettings.DEPART_TIME
    except Exception:
        assert False
