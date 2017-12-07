import pytest

from collections import namedtuple

from pendulum import Interval, Pendulum

from d3a.models.area import DEFAULT_CONFIG
from d3a.models.budget_keeper import BudgetKeeper


class FakeOffer(namedtuple('FakeOffer', 'price buyer seller')):
    pass


class FakeTrade:
    def __init__(self, offer_price, buyer_name='FakeChild', seller_name='FakeArea'):
        self.offer_price = offer_price
        self.seller_name = seller_name
        self.buyer_name = buyer_name

    @property
    def offer(self):
        return FakeOffer(self.offer_price, self.buyer_name, self.seller_name)


class FakeMarket(namedtuple('FakeMarket', 'trades')):
    pass


class FakeArea:
    def __init__(self):
        self.log = FakeLog()
        self.children = [FakeChild(i) for i in range(3)]
        self.current_trades = []

    @property
    def config(self):
        return DEFAULT_CONFIG

    @property
    def now(self):
        return Pendulum.now()

    @property
    def current_market(self):
        return FakeMarket(self.current_trades)

    @property
    def name(self):
        return "FakeArea"


class FakeLog:
    def info(self, message):
        pass

    def warning(self, message):
        pass


class FakeChild:
    def __init__(self, id):
        self.id = id
        self.strategy = FakeStrategy()

    @property
    def name(self):
        return "FakeChild{}".format(self.id)


class FakeStrategy:
    def __init__(self):
        self.fired_trigger = None

    def fire_trigger(self, trigger):
        self.fired_trigger = trigger


@pytest.fixture
def keeper():
    fixture = BudgetKeeper(FakeArea(), 10.0, Interval(days=1))
    fixture.event_activate()
    return fixture


def test_budget_keeper_decide(keeper):
    keeper.forecast = {child: 0.04 for child in keeper.area.children}
    keeper.set_priority(keeper.area.children[1], 1)
    keeper.decide()
    assert keeper.area.children[0].strategy.fired_trigger == "enable"
    assert keeper.area.children[1].strategy.fired_trigger == "disable"
    assert keeper.area.children[2].strategy.fired_trigger == "enable"


@pytest.fixture
def keeper2(keeper):
    keeper.area.current_trades = [FakeTrade(0.1, 'FakeChild2'),
                                  FakeTrade(0.005, 'FakeChild1'),
                                  FakeTrade(0.02, 'FakeChild0'),
                                  FakeTrade(0.015, 'FakeChild1')]
    return keeper


def test_budget_keeper_compute_remaining(keeper2):
    assert keeper2.remaining == 10.0
    keeper2.compute_remaining()
    assert keeper2.remaining == 9.86


def test_budget_keeper_update_forecast(keeper2):
    keeper2.update_forecast()
    assert keeper2.forecast[keeper2.area.children[2]] == pytest.approx(0.1)
    assert keeper2.forecast[keeper2.area.children[1]] == pytest.approx(0.02)


def test_budget_keeper_disables_high_consumer(keeper2):
    keeper2.event_market_cycle()
    assert keeper2.area.children[2].strategy.fired_trigger == "disable"


def test_budget_keeper_does_not_disable_other_consumers(keeper2):
    keeper2.event_market_cycle()
    assert keeper2.area.children[0].strategy.fired_trigger == "enable"
    assert keeper2.area.children[1].strategy.fired_trigger == "enable"
