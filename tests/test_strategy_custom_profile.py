import pytest

from pendulum import Interval, Pendulum

from d3a.models.area import DEFAULT_CONFIG
from d3a.models.strategy.custom_profile import CustomProfileStrategy


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
    def __init__(self, strategy):
        self.strategy = strategy
        self.value = 20
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


def test_custom_profile_over_period(profile):
    assert profile.amount_over_period(Pendulum(2017, 1, 1, 0, 1), Interval(minutes=2)) == 0.1
    assert profile.amount_over_period(Pendulum(2017, 1, 1, 0, 0), Interval(minutes=5)) == 0.25


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
