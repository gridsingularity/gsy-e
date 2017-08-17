import pytest

from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.area import DEFAULT_CONFIG
from d3a.models.strategy.const import MAX_FRIDGE_TEMP


class FakeOwner:
    @property
    def name(self):
        return "Owner"


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


# surplus energy is reported

def test_fridge_report_energy_surplus(fridge_fixture):
    fridge_fixture.report_energy(10)
    assert fridge_fixture.area.reported_value>0


# no report if there is no surplus or deficit

def test_fridge_report_energy_balanced(fridge_fixture):
    fridge_fixture.report_energy(0)
    assert fridge_fixture.area.reported_value is None


# need for more energy is reported if we have none but need to cool down

def test_fridge_report_energy_too_warm(fridge_fixture):
    fridge_fixture.temperature = MAX_FRIDGE_TEMP+1
    fridge_fixture.report_energy(0)
    assert fridge_fixture.area.reported_value<0
