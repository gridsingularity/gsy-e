import pytest

from pendulum import Interval, Pendulum

from d3a.models.area import DEFAULT_CONFIG
from d3a.models.strategy.custom_profile import CustomProfileStrategy, \
    CustomProfileIrregularTimes, custom_profile_strategy_from_csv


class FakeArea:
    @property
    def config(self):
        return DEFAULT_CONFIG

    @property
    def current_slot(self):
        return 5

    @property
    def markets(self):
        return {
            Pendulum(2017, 1, 1, 0, 0): FakeMarket(),
            Pendulum(2017, 1, 1, 0, 15): FakeMarket()
        }


class FakeCustomProfile:
    def __init__(self, strategy, value=20):
        self.strategy = strategy
        self.value = value
        self.factor = 1/60.0

    def amount_over_period(self, period_start, duration):
        return self.value


class FakeMarket:
    def __init__(self):
        self.offer_energy = 10

    @property
    def sorted_offers(self):
        return [FakeOffer(self.offer_energy)] * 10


class FakeOffer:
    def __init__(self, energy):
        self.energy = energy


@pytest.fixture
def fake_area():
    return FakeArea()


@pytest.fixture
def profile(fake_area):
    strategy = CustomProfileStrategy(fake_area)
    strategy.profile.set_from_list([5.5, 2.9, 3.1, 2.5, 1.0],
                                   Pendulum(2017, 1, 1),
                                   Interval(minutes=1))
    return strategy.profile


def test_custom_profile_set_from_list(profile):
    assert profile.power_at(Pendulum(2016, 12, 31)) == 0.0
    assert profile.power_at(Pendulum(2017, 1, 1, 0, 2)) == 3.1
    assert profile.power_at(Pendulum(2017, 1, 1, 0, 3)) == 2.5
    assert profile.power_at(Pendulum(2017, 1, 1, 0, 7)) == 0.0


def test_custom_profile_amount_over_period(profile):
    assert profile.amount_over_period(Pendulum(2017, 1, 1, 0, 1), Interval(minutes=2)) == 0.1
    assert profile.amount_over_period(Pendulum(2017, 1, 1, 0, 0), Interval(minutes=5)) == 0.25


@pytest.fixture
def profile_irreg(fake_area):
    strategy = CustomProfileStrategy(fake_area, profile_type=CustomProfileIrregularTimes)
    data = {
        Pendulum(2017, 1, 1, 0, 10): 3.0,
        Pendulum(2017, 1, 1, 0, 11): 14.0,
        Pendulum(2017, 1, 1, 0, 15): 14.0,
        Pendulum(2017, 1, 1, 0, 16): 11.0
    }
    strategy.profile.set_from_dict(data)
    return strategy.profile


def test_irregular_times_power_at(profile_irreg):
    assert profile_irreg.power_at(Pendulum(2017, 1, 1, 0, 8)) == 0.0
    assert profile_irreg.power_at(Pendulum(2017, 1, 1, 0, 10)) == 3.0
    assert profile_irreg.power_at(Pendulum(2017, 1, 1, 0, 11)) == 14.0
    assert profile_irreg.power_at(Pendulum(2017, 1, 1, 0, 16, 1)) == 0.0


def test_irregular_times_amount_over_period(profile_irreg):
    start = Pendulum(2017, 1, 1, 0, 11)
    assert profile_irreg.amount_over_period(start, Interval(minutes=4)) == 56.0


def test_irregular_times_amount_over_period_early_end(profile_irreg):
    start = Pendulum(2017, 1, 1, 0, 11)
    assert profile_irreg.amount_over_period(start, Interval(minutes=3)) == 42.0


def test_irregular_times_amount_over_period_late_begin(profile_irreg):
    start = Pendulum(2017, 1, 1, 0, 13)
    assert profile_irreg.amount_over_period(start, Interval(minutes=2)) == 28.0


def test_read_from_csv(fake_area):
    data = ('2017-01-01T00:10:00,17.4', '2017-01-01T00:19:00,3.1', '2017-01-01T00:41:00,3.1')
    testee = custom_profile_strategy_from_csv(fake_area, data)
    assert testee.profile.power_at(Pendulum(2017, 1, 1, 0, 10)) == 17.4
    assert testee.profile.power_at(Pendulum(2017, 1, 1, 0, 40)) == 3.1


@pytest.fixture
def strategy(fake_area):
    return CustomProfileStrategy(fake_area, profile_type=FakeCustomProfile)


def test_event_activate(strategy):
    strategy.event_activate()
    assert list(strategy.slot_load.values()) == [20, 20]


@pytest.fixture
def strategy2(strategy, called):
    strategy.accept_offer = called
    strategy.event_activate()
    return strategy


def test_buys_right_amount(strategy2):
    strategy2.event_tick(area=strategy2.area)
    assert list(strategy2.bought.values()) == [20, 20]
    assert len(strategy2.accept_offer.calls) == 4


@pytest.fixture
def strategy3(strategy, called):
    strategy.profile.value = 17
    strategy.accept_offer = called
    strategy.event_activate()
    return strategy


def test_buys_partial_offer(strategy3):
    strategy3.event_tick(area=strategy3.area)
    assert list(strategy3.bought.values()) == [17, 17]
