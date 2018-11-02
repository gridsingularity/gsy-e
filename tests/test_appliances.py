from collections import defaultdict

import pytest
from unittest.mock import MagicMock

from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import DEFAULT_CONFIG
from d3a.models.area.stats import AreaStats

from pendulum import DateTime
from d3a import TIME_ZONE


class FakeSwitchableStrategy:
    def energy_balance(self, _):
        return 5


class FakePVStrategy:
    def energy_balance(self, _):
        return 1

    def __init__(self):
        self.panel_count = 1


class FakeCustomProfileStrategy:
    def __init__(self, bought, slot_load):
        self.bought_val = bought
        self.slot_load_val = slot_load

    @property
    def bought(self):
        return defaultdict(lambda: self.bought_val)

    @property
    def slot_load(self):
        return defaultdict(lambda: self.slot_load_val)


class FakeOwner:
    @property
    def name(self):
        return "Owner"


class FakeOwnerWithStrategy(FakeOwner):
    def __init__(self, strategy):
        self._strategy = strategy

    @property
    def strategy(self):
        return self._strategy


class FakeOwnerWithStrategyAndMarket(FakeOwnerWithStrategy):
    def __init__(self, strategy):
        super().__init__(strategy)

    @property
    def current_market(self):
        return FakeCurrentMarket()


class FakeCurrentMarket:
    @property
    def time_slot(self):
        return "time_slot"


class FakeArea:
    def __init__(self):
        self.reported_value = None
        self.is_nighttime = False
        self.stats = MagicMock(spec=AreaStats)
        self.stats.report_accounting = self.report_accounting

    def report_accounting(self, market, owner, value, time):
        self.reported_value = value

    @property
    def config(self):
        return DEFAULT_CONFIG

    @property
    def now(self):
        return DateTime.now(tz=TIME_ZONE)

    @property
    def current_market(self):
        return "market"

    def set_nighttime(self, is_nighttime):
        self.is_nighttime = is_nighttime

    @property
    def current_tick(self):
        if self.is_nighttime:
            return 4
        else:
            return int(36000 / DEFAULT_CONFIG.tick_length.in_seconds())
            # 10 AM so the output of the PV is >0


@pytest.fixture
def switchable_fixture():
    switchable = SwitchableAppliance()
    switchable.area = FakeArea()
    switchable.owner = FakeOwnerWithStrategy(FakeSwitchableStrategy())
    return switchable


# on by default, can be switched on/off with its triggers

def test_switchable_appliance_switching(switchable_fixture):
    assert switchable_fixture.is_on
    switchable_fixture.fire_trigger("off")
    assert not switchable_fixture.is_on
    switchable_fixture.fire_trigger("on")
    assert switchable_fixture.is_on


# trades/reports only when switched on

def test_switchable_appliance_reports_when_on(switchable_fixture):
    switchable_fixture.event_tick(area=switchable_fixture.area)
    assert switchable_fixture.area.reported_value is not None


def test_switchable_appliance_no_report_when_off(switchable_fixture):
    switchable_fixture.fire_trigger("off")
    switchable_fixture.event_tick(area=switchable_fixture.area)
    assert switchable_fixture.area.reported_value is None


@pytest.fixture
def pv_fixture():
    pv = PVAppliance()
    pv.area = FakeArea()
    pv.owner = FakeOwnerWithStrategy(FakePVStrategy())
    pv.event_activate()
    return pv


# has energy at all cloud cover percentages except 100%

def test_pv_appliance_cloud_cover(pv_fixture):
    pv_fixture.trigger_cloud_cover(percent=100.0, duration=10)
    pv_fixture.report_energy(1)
    assert pv_fixture.area.reported_value == 0.02
    pv_fixture.trigger_cloud_cover(percent=95.0, duration=10)
    pv_fixture.report_energy(1)
    assert round(pv_fixture.area.reported_value, 3) == 0.05
    pv_fixture.cloud_duration = 0
    pv_fixture.report_energy(1)
    assert pv_fixture.area.reported_value == 1
