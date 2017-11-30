import pytest

from pendulum import Interval, Pendulum

from d3a.models.area import DEFAULT_CONFIG
from d3a.models.budget_keeper import BudgetKeeper


class FakeArea:
    def __init__(self):
        self.log = FakeLog()
        self.children = [FakeChild(i) for i in range(3)]

    @property
    def config(self):
        return DEFAULT_CONFIG

    @property
    def now(self):
        return Pendulum.now()


class FakeLog:
    def info(self, message):
        pass

    def warning(self, message):
        pass


class FakeChild:
    def __init__(self, id):
        self.id = id
        self.strategy = FakeStrategy()


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
