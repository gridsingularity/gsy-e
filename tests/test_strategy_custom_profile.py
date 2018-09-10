import pytest

from pendulum import duration, DateTime

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
    def name(self):
        return 'FakeArea'


class FakeParent(FakeArea):
    def __init__(self):
        self.markets = {
            DateTime(2017, 1, 1, 0, 0): FakeMarket(),
            DateTime(2017, 1, 1, 0, 15): FakeMarket()
        }


class FakeOwner(FakeArea):
    def __init__(self):
        self.parent = FakeParent()


class FakeCustomProfile:
    def __init__(self, strategy, value=20):
        self.strategy = strategy
        self.value = value
        self.factor = 1/60.0
        self.start_time = DateTime(2017, 1, 1, 0, 0)

    def amount_over_period(self, period_start, duration):
        return self.value


class FakeMarket:
    def __init__(self):
        self.offer_energy = 10
        self.received_offer = None

    @property
    def sorted_offers(self):
        return [FakeOffer(self.offer_energy)] * 10

    def offer(self, price, energy, seller):
        self.received_offer = FakeOffer(energy, price, seller)


class FakeOffer:
    def __init__(self, energy, price=None, seller=None):
        self.energy = energy
        self.price = price
        self.seller = seller


@pytest.fixture
def fake_owner():
    return FakeOwner()


@pytest.fixture
def profile(fake_owner):
    strategy = CustomProfileStrategy()
    strategy.owner = fake_owner
    strategy.consumption.set_from_list([5.5, 2.9, 3.1, 2.5, 1.0],
                                       DateTime(2017, 1, 1),
                                       duration(minutes=1))
    return strategy.consumption


def test_custom_profile_set_from_list(profile):
    assert profile.power_at(DateTime(2016, 12, 31)) == 0.0
    assert profile.power_at(DateTime(2017, 1, 1, 0, 2)) == 3.1
    assert profile.power_at(DateTime(2017, 1, 1, 0, 3)) == 2.5
    assert profile.power_at(DateTime(2017, 1, 1, 0, 7)) == 0.0


def test_custom_profile_amount_over_period(profile):
    assert profile.amount_over_period(DateTime(2017, 1, 1, 0, 1), duration(minutes=2)) == 0.1
    assert profile.amount_over_period(DateTime(2017, 1, 1, 0, 0), duration(minutes=5)) == 0.25


def test_custom_profile_amount_over_period_fractioned(profile):
    profile.set_from_list([0.0, 1.0, 2.0, 3.0, 4.0], DateTime(2017, 1, 1), duration(hours=1))
    assert profile.amount_over_period(DateTime(2017, 1, 1, 0, 30), duration(minutes=45)) == 0.25
    assert profile.amount_over_period(DateTime(2017, 1, 1, 1, 5), duration(minutes=30)) == 0.5
    assert profile.amount_over_period(DateTime(2017, 1, 1, 1, 45), duration(hours=2)) == 4.5


@pytest.fixture
def profile_irreg(fake_owner):
    strategy = CustomProfileStrategy(profile_type=CustomProfileIrregularTimes)
    strategy.owner = fake_owner
    data = {
        DateTime(2017, 1, 1, 0, 10): 3.0,
        DateTime(2017, 1, 1, 0, 11): 14.0,
        DateTime(2017, 1, 1, 0, 15): 14.0,
        DateTime(2017, 1, 1, 0, 16): 11.0
    }
    strategy.consumption.set_from_dict(data)
    return strategy.consumption


def test_irregular_times_power_at(profile_irreg):
    assert profile_irreg.power_at(DateTime(2017, 1, 1, 0, 8)) == 0.0
    assert profile_irreg.power_at(DateTime(2017, 1, 1, 0, 10)) == 3.0
    assert profile_irreg.power_at(DateTime(2017, 1, 1, 0, 11)) == 14.0
    assert profile_irreg.power_at(DateTime(2017, 1, 1, 0, 16, 1)) == 0.0


def test_irregular_times_amount_over_period(profile_irreg):
    start = DateTime(2017, 1, 1, 0, 11)
    assert profile_irreg.amount_over_period(start, duration(minutes=4)) == 56.0


def test_irregular_times_amount_over_period_early_end(profile_irreg):
    start = DateTime(2017, 1, 1, 0, 11)
    assert profile_irreg.amount_over_period(start, duration(minutes=3)) == 42.0


def test_irregular_times_amount_over_period_late_begin(profile_irreg):
    start = DateTime(2017, 1, 1, 0, 13)
    assert profile_irreg.amount_over_period(start, duration(minutes=2)) == 28.0


def test_read_from_csv(fake_owner):
    cons = ('2017-01-01T00:10:00,17.4', '2017-01-01T00:19:00,3.1', '2017-01-01T00:41:00,3.1')
    prod = ('2017-01-01T00:10:00,11.3', '2017-01-01T00:16:00,8.0', '2017-01-01T00:30:00,8.0')
    testee = custom_profile_strategy_from_csv(cons, prod)
    from pendulum import timezone
    tz = timezone('UTC')
    assert testee.consumption.power_at(DateTime(2017, 1, 1, 0, 10, tzinfo=tz)) == 17.4
    assert testee.consumption.power_at(DateTime(2017, 1, 1, 0, 40, tzinfo=tz)) == 3.1
    assert testee.production.power_at(DateTime(2017, 1, 1, 0, 10, tzinfo=tz)) == 11.3
    assert testee.production.power_at(DateTime(2017, 1, 1, 0, 18, tzinfo=tz)) == 8.0


@pytest.fixture
def strategy(fake_owner):
    strategy = CustomProfileStrategy(profile_type=FakeCustomProfile)
    strategy.owner = fake_owner
    strategy.production.value = 15
    return strategy


def test_event_activate(strategy):
    strategy.event_activate()
    assert list(strategy.slot_load.values()) == [20, 20]
    assert list(strategy.slot_prod.values()) == [15, 15]


@pytest.fixture
def strategy2(strategy, called):
    strategy.production.value = 0
    strategy.accept_offer = called
    strategy.event_activate()
    return strategy


def test_buys_right_amount(strategy2):
    strategy2.event_tick(area=strategy2.owner.parent)
    assert list(strategy2.bought.values()) == [20, 20]
    assert len(strategy2.accept_offer.calls) == 4


@pytest.fixture
def strategy3(strategy, called):
    strategy.consumption.value = 17
    strategy.production.value = 0
    strategy.accept_offer = called
    strategy.event_activate()
    return strategy


def test_buys_partial_offer(strategy3):
    strategy3.event_tick(area=strategy3.owner.parent)
    assert list(strategy3.bought.values()) == [17, 17]


@pytest.fixture
def strategy4(strategy):
    strategy.consumption.value = 0
    strategy.production.value = 5
    strategy.event_activate()
    return strategy


def test_offers(strategy4):
    strategy4.event_tick(area=strategy4.owner.parent)
    for market in strategy4.owner.parent.markets.values():
        assert market.received_offer.price == strategy4.offer_price * market.received_offer.energy
        assert market.received_offer.seller == strategy4.owner.name
