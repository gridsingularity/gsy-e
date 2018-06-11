import pytest
import unittest
import pendulum
from unittest.mock import MagicMock, Mock
from datetime import timedelta
from pendulum import Pendulum
from pendulum.interval import Interval
from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market import Offer
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy

TIME = pendulum.today().at(hour=10, minute=45, second=2)

MIN_BUY_ENERGY = 50  # wh


class FakeArea:
    def __init__(self, count):
        self.appliance = None
        self.name = 'FakeArea'
        self.count = count

    @property
    def config(self):
        return DEFAULT_CONFIG

    @property
    def current_tick(self):
        return 5

    @property
    def now(self) -> Pendulum:
        """
        Return the 'current time' as a `Pendulum` object.
        Can be overridden in subclasses to change the meaning of 'now'.

        In this default implementation 'current time' is defined by the number of ticks that
        have passed.
        """
        return Pendulum.now().start_of('day').add_timedelta(
            timedelta(hours=10) + self.config.tick_length * self.current_tick
        )

    @property
    def next_market(self):
        return FakeMarket(15)


class FakeMarket:
    def __init__(self, count):
        self.count = count
        self.most_affordable_energy = 0.1551

    @property
    def sorted_offers(self):
        offers = [
            [
                Offer('id', 1, (MIN_BUY_ENERGY/1000), 'A', self),  # Energyprice is 1
                Offer('id', 2, (MIN_BUY_ENERGY/1000), 'A', self),  # Energyprice is 2
                Offer('id', 3, (MIN_BUY_ENERGY/1000), 'A', self),  # Energyprice is 3
                Offer('id', 4, (MIN_BUY_ENERGY/1000), 'A', self),  # Energyprice is 4
            ],
            [
                Offer('id', 1, (MIN_BUY_ENERGY * 0.033 / 1000), 'A', self),
                Offer('id', 2, (MIN_BUY_ENERGY * 0.033 / 1000), 'A', self)
            ],
            [
                Offer('id', 1, 5, 'A', self),
                Offer('id2', 2, (MIN_BUY_ENERGY / 1000), 'A', self)
            ]
        ]
        return offers[self.count]

    @property
    def most_affordable_offers(self):
        return [Offer('id_affordable', 1, self.most_affordable_energy, 'A', self)]

    @property
    def time_slot(self):
        return Pendulum.now().start_of('day').add_timedelta(timedelta(hours=10))


class TestLoadHoursStrategyInput(unittest.TestCase):

    def setUp(self):
        self.appliance = MagicMock(spec=SimpleAppliance)
        self.strategy1 = MagicMock(spec=LoadHoursStrategy)

    def tearDown(self):
        pass

    def area_test(self):
        area = FakeArea(0)
        area.current_market = FakeMarket(0)
        area.markets = {TIME: FakeMarket(0)}
        return area

    def Mock_LoadHoursStrategy(self, avg_power_W, hrs_per_day, hrs_of_day):
        strategy = LoadHoursStrategy(avg_power_W=avg_power_W,
                                     hrs_per_day=hrs_per_day,
                                     hrs_of_day=hrs_of_day)
        strategy.area = self.area_test()
        strategy.owner = self.area_test()
        strategy.event_activate()
        return strategy

    def test_LoadHoursStrategy_input(self):
        power_W = 620
        self.assertEqual(
            self.Mock_LoadHoursStrategy(
                power_W, 4, [1, 2, 3, 4]).daily_energy_required.m,  power_W * 4)
        self.assertEqual(
            self.Mock_LoadHoursStrategy(
                power_W, None, [1, 2, 3, 4]).daily_energy_required.m, power_W * 4)
        self.assertEqual(
            self.Mock_LoadHoursStrategy(
                power_W, 4, [1, 2, 3, 4, 5, 6]).daily_energy_required.m, power_W * 4)
        self.assertEqual(
            self.Mock_LoadHoursStrategy(
                power_W, 4, None).daily_energy_required.m, power_W * 4)
        with self.assertRaises(ValueError):
            self.Mock_LoadHoursStrategy(power_W, 4, [1, 2])


@pytest.fixture()
def area_test1(market_test1):
    area = FakeArea(0)
    area.current_market = market_test1
    area.markets = {TIME: market_test1}
    return area


@pytest.fixture
def area_test2(market_test2):
    area = FakeArea(0)
    area.current_market = market_test2
    area.markets = {TIME: market_test2}
    return area


@pytest.fixture()
def market_test1():
    return FakeMarket(0)


@pytest.fixture
def market_test2():
    return FakeMarket(2)


@pytest.fixture
def load_hours_strategy_test(called):
    strategy = LoadHoursStrategy(avg_power_W=620, hrs_per_day=4, hrs_of_day=[8, 9, 10, 12])
    strategy.accept_offer = called
    return strategy


@pytest.fixture
def load_hours_strategy_test1(load_hours_strategy_test, area_test1):
    load_hours_strategy_test.area = area_test1
    load_hours_strategy_test.owner = area_test1
    return load_hours_strategy_test


@pytest.fixture
def load_hours_strategy_test2(load_hours_strategy_test, area_test2):
    load_hours_strategy_test.area = area_test2
    load_hours_strategy_test.owner = area_test2
    return load_hours_strategy_test


@pytest.fixture
def load_hours_strategy_test4():
    strategy = LoadHoursStrategy(avg_power_W=620, hrs_per_day=4, hrs_of_day=[8, 9, 10, 12])
    strategy.accept_offer = Mock()
    strategy.accept_offer.call_args
    return strategy


@pytest.fixture
def load_hours_strategy_test5(load_hours_strategy_test4, area_test2):
    load_hours_strategy_test4.area = area_test2
    load_hours_strategy_test4.owner = area_test2
    return load_hours_strategy_test4


# Test if daily energy requirement is calculated correctly for the device
def test_calculate_daily_energy_req(load_hours_strategy_test1):
    load_hours_strategy_test1.event_activate()
    assert load_hours_strategy_test1.daily_energy_required.m == 620*4


# Test if daily energy requirement is calculated correctly for the device
def test_activate_event_populates_energy_requirement(load_hours_strategy_test1):
    load_hours_strategy_test1.event_activate()
    assert load_hours_strategy_test1.energy_requirement == \
        load_hours_strategy_test1.energy_per_slot_Wh.m
    ts = load_hours_strategy_test1.area.next_market.time_slot
    assert load_hours_strategy_test1.state.desired_energy[ts] == \
        load_hours_strategy_test1.energy_requirement


# Test if device accepts the most affordable offer
def test_device_accepts_offer(load_hours_strategy_test1, market_test1):
    load_hours_strategy_test1.event_activate()
    cheapest_offer = market_test1.most_affordable_offers[0]
    load_hours_strategy_test1.energy_requirement = cheapest_offer.energy * 1000 + 1
    load_hours_strategy_test1.event_tick(area=area_test1)
    assert load_hours_strategy_test1.accept_offer.calls[0][0][1] == repr(cheapest_offer)


def test_event_market_cycle(load_hours_strategy_test1, market_test1):
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.area.past_markets = {TIME: market_test1}
    load_hours_strategy_test1.event_market_cycle()
    assert load_hours_strategy_test1.energy_requirement == \
        load_hours_strategy_test1.energy_per_slot_Wh.m


def test_event_market_cycle_resets_energy_requirement(load_hours_strategy_test1, market_test1):
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.area.past_markets = {TIME: market_test1}
    load_hours_strategy_test1.energy_requirement = 150.0
    load_hours_strategy_test1.event_market_cycle()
    assert load_hours_strategy_test1.energy_requirement == \
        load_hours_strategy_test1.energy_per_slot_Wh.m
    load_hours_strategy_test1.energy_requirement += 1000000.0
    load_hours_strategy_test1.event_market_cycle()
    assert load_hours_strategy_test1.energy_requirement == \
        load_hours_strategy_test1.energy_per_slot_Wh.m


def test_event_tick(load_hours_strategy_test1, market_test1):
    market_test1.most_affordable_energy = 0.155
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.area.past_markets = {TIME: market_test1}
    load_hours_strategy_test1.event_market_cycle()
    load_hours_strategy_test1.event_tick(area=area_test1)
    assert load_hours_strategy_test1.energy_requirement == 0
    market_test1.most_affordable_energy = 0.154
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.area.past_markets = {TIME: market_test1}
    load_hours_strategy_test1.event_market_cycle()
    load_hours_strategy_test1.event_tick(area=area_test1)
    assert load_hours_strategy_test1.energy_requirement == 0.001 * 1000.0


def test_event_tick_with_partial_offer(load_hours_strategy_test2, market_test2):
    market_test2.most_affordable_energy = 0.156
    load_hours_strategy_test2.event_activate()
    load_hours_strategy_test2.area.past_markets = {TIME: market_test2}
    load_hours_strategy_test2.event_market_cycle()
    requirement = load_hours_strategy_test2.energy_requirement / 1000
    load_hours_strategy_test2.event_tick(area=area_test2)
    assert load_hours_strategy_test2.energy_requirement == 0
    assert float(load_hours_strategy_test2.accept_offer.calls[0][1]['energy']) == requirement


def test_load_hours_constructor_rejects_incorrect_hrs_of_day():
    with pytest.raises(ValueError):
        LoadHoursStrategy(100, hrs_of_day=[12, 13, 24])


def test_device_operating_hours_deduction_with_partial_trade(load_hours_strategy_test5,
                                                             market_test2):
    market_test2.most_affordable_energy = 0.1
    load_hours_strategy_test5.event_activate()
    load_hours_strategy_test5.area.past_markets = {TIME: market_test2}
    load_hours_strategy_test5.event_market_cycle()
    load_hours_strategy_test5.event_tick(area=area_test2)
    assert round(((float(load_hours_strategy_test5.accept_offer.call_args[0][1].energy) *
                   1000 / load_hours_strategy_test5.energy_per_slot_Wh.m) *
                  (load_hours_strategy_test5.area.config.slot_length / Interval(hours=1))), 2) == \
        round(((0.1/0.155) * 0.25), 2)
