"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import pytest

from collections import namedtuple

from pendulum import DateTime

from d3a.constants import TIME_ZONE
from d3a.models.area import DEFAULT_CONFIG
from d3a.models.budget_keeper import BudgetKeeper
from d3a.d3a_core.util import make_iaa_name


FakeOffer = namedtuple('FakeOffer', 'price seller')
FakeMarket = namedtuple('FakeMarket', 'trades')


class FakeLog:
    def info(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        pass


class FakeChild:
    def __init__(self, id):
        self.id = id
        self.strategy = FakeStrategy()

    @property
    def name(self):
        return "FakeChild{}".format(self.id)

    def _fire_trigger(self, trigger):
        self.strategy.fire_trigger(trigger)


class FakeStrategy:
    def __init__(self):
        self.fired_trigger = None

    def fire_trigger(self, trigger):
        self.fired_trigger = trigger


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
        return DateTime.now(tz=TIME_ZONE)

    @property
    def current_market(self):
        return FakeMarket(self.current_trades)

    @property
    def name(self):
        return "FakeArea"


class FakeTrade:
    def __init__(self, offer_price, buyer='FakeChild', seller=make_iaa_name(FakeArea())):
        self.offer_price = offer_price
        self.seller = seller
        self.buyer = buyer

    @property
    def offer(self):
        return FakeOffer(self.offer_price, self.seller)


@pytest.fixture
def keeper():
    fixture = BudgetKeeper(10.0, 1, FakeArea())
    fixture.activate()
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
    keeper2.process_market_cycle()
    assert keeper2.area.children[2].strategy.fired_trigger == "disable"


def test_budget_keeper_does_not_disable_other_consumers(keeper2):
    keeper2.process_market_cycle()
    assert keeper2.area.children[0].strategy.fired_trigger == "enable"
    assert keeper2.area.children[1].strategy.fired_trigger == "enable"
