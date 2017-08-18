import pytest

from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import DEFAULT_CONFIG
from d3a.models.strategy.const import MAX_FRIDGE_TEMP


class FakeOwnerStrategy:
    def energy_balance(self,_):
        return 5


class FakeOwner:
    @property
    def name(self):
        return "Owner"


class FakeOwnerWithStrategy(FakeOwner):
    @property
    def strategy(self):
        return FakeOwnerStrategy()


class FakeArea:
    def __init__(self):
        self.reported_value = None

    def report_accounting(self,market,owner,value):
        self.reported_value = value

    @property
    def config(self):
        return DEFAULT_CONFIG

    @property
    def current_market(self):
        return "market"


@pytest.fixture
def fridge_fixture():
    fridge = FridgeAppliance()
    fridge.area = FakeArea()
    fridge.owner = FakeOwner()
    return fridge


# door is closed by default and can be opened/closed by class-specfic triggers

def test_fridge_door(fridge_fixture):
    assert not fridge_fixture.is_door_open
    fridge_fixture.fire_trigger("open")
    assert fridge_fixture.is_door_open
    fridge_fixture.fire_trigger("close")
    assert not fridge_fixture.is_door_open


# reports traded surplus energy

def test_fridge_report_energy_surplus(fridge_fixture):
    fridge_fixture.report_energy(10)
    assert fridge_fixture.area.reported_value>0


# no report if there is no surplus or deficit

def test_fridge_report_energy_balanced(fridge_fixture):
    fridge_fixture.report_energy(0)
    assert fridge_fixture.area.reported_value is None


# always buys energy if we have none and upper temperature constraint is violated

def test_fridge_report_energy_too_warm(fridge_fixture):
    fridge_fixture.temperature = MAX_FRIDGE_TEMP+1
    fridge_fixture.report_energy(0)
    assert fridge_fixture.area.reported_value<0


@pytest.fixture
def switchable_fixture():
    switchable = SwitchableAppliance()
    switchable.area = FakeArea()
    switchable.owner = FakeOwnerWithStrategy()
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

