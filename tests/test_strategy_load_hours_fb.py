import pytest
import pendulum
from datetime import timedelta
from pendulum import Pendulum
from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market import Offer
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
    def time_slot(self):
        return Pendulum.now().start_of('day').add_timedelta(timedelta(hours=10))


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
    strategy = LoadHoursStrategy(avg_power=620, hrs_per_day=4, hrs_of_day=(8, 12))
    strategy.accept_offer = called
    if 10 not in strategy.active_hours:
        strategy.active_hours.pop()
        strategy.active_hours.add(10)
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


# Test if daily energy requirement is calculated correctly for the device
def test_calculate_daily_energy_req(load_hours_strategy_test1):
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.daily_energy_required = 620*4


# Test if device accepts the cheapest offer
def test_device_accepts_offer(load_hours_strategy_test1, market_test1):
    load_hours_strategy_test1.event_activate()
    cheapest_offer = market_test1.sorted_offers[0]
    load_hours_strategy_test1.energy_requirement = cheapest_offer.energy * 1000 + 1
    load_hours_strategy_test1.event_tick(area=area_test1)
    assert load_hours_strategy_test1.accept_offer.calls[0][0][1] == repr(cheapest_offer)


def test_event_market_cycle(load_hours_strategy_test1, market_test1):
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.area.past_markets = {TIME: market_test1}
    load_hours_strategy_test1.event_market_cycle()
    assert load_hours_strategy_test1.energy_requirement == \
        load_hours_strategy_test1.energy_per_slot


def test_event_market_cycle_resets_energy_requirement(load_hours_strategy_test1, market_test1):
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.area.past_markets = {TIME: market_test1}
    load_hours_strategy_test1.energy_requirement = 150.0
    load_hours_strategy_test1.event_market_cycle()
    assert load_hours_strategy_test1.energy_requirement == \
        load_hours_strategy_test1.energy_per_slot
    load_hours_strategy_test1.energy_requirement += 1000000.0
    load_hours_strategy_test1.event_market_cycle()
    assert load_hours_strategy_test1.energy_requirement == \
        load_hours_strategy_test1.energy_per_slot


def test_event_tick(load_hours_strategy_test1, market_test1):
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.area.past_markets = {TIME: market_test1}
    load_hours_strategy_test1.event_market_cycle()
    load_hours_strategy_test1.event_tick(area=area_test1)
    assert load_hours_strategy_test1.energy_requirement == \
        load_hours_strategy_test1.energy_per_slot - market_test1.sorted_offers[0].energy * 1000


def test_event_tick_with_partial_offer(load_hours_strategy_test2, market_test2):
    load_hours_strategy_test2.event_activate()
    load_hours_strategy_test2.area.past_markets = {TIME: market_test2}
    load_hours_strategy_test2.event_market_cycle()
    requirement = load_hours_strategy_test2.energy_requirement / 1000
    load_hours_strategy_test2.event_tick(area=area_test2)
    assert load_hours_strategy_test2.energy_requirement == 0
    assert float(load_hours_strategy_test2.accept_offer.calls[0][1]['energy']) == requirement
