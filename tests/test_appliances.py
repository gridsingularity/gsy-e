from copy import deepcopy

import pytest

from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import DEFAULT_CONFIG
from d3a.models.strategy.const import MAX_FRIDGE_TEMP, FRIDGE_TEMPERATURE


class FakeSwitchableStrategy:
    def energy_balance(self, _):
        return 5


class FakePVStrategy:
    def energy_balance(self, _):
        return 1

    def __init__(self):
        self.panel_count = 1


class FakeFridgeState:
    def __init__(self):
        self.temperature = FRIDGE_TEMPERATURE
        self.max_temperature = MAX_FRIDGE_TEMP


class FakeFridgeStrategy:
    @property
    def fridge_temp(self):
        return FRIDGE_TEMPERATURE

    @property
    def state(self):
        return FakeFridgeState()

    def post(self, **data):
        pass


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


class FakeArea:
    def __init__(self):
        self.reported_value = None
        self.is_nighttime = False

    def report_accounting(self, market, owner, value):
        self.reported_value = value

    @property
    def config(self):
        return DEFAULT_CONFIG

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
def fridge_fixture():
    fridge = FridgeAppliance()
    fridge.area = FakeArea()
    fridge_strategy = FakeFridgeStrategy()
    fridge.owner = FakeOwnerWithStrategy(fridge_strategy)
    fridge.state = FakeFridgeState()
    fridge.event_activate()
    return fridge


# door is closed by default and can be opened/closed by class-specfic triggers

def test_fridge_appliance_door(fridge_fixture):
    assert not fridge_fixture.is_door_open
    fridge_fixture.fire_trigger("open")
    assert fridge_fixture.is_door_open
    fridge_fixture.fire_trigger("close")
    assert not fridge_fixture.is_door_open


# reports traded surplus energy

def test_fridge_appliance_report_energy_surplus(fridge_fixture):
    test_energy = 10
    fridge_fixture.report_energy(test_energy)
    assert fridge_fixture.area.reported_value > 0


# no report if there is no surplus or deficit

def test_fridge_appliance_report_energy_balanced(fridge_fixture):
    fridge_fixture.report_energy(0)
    assert fridge_fixture.area.reported_value is None


# temperature rises when the door is open

def test_fridge_appliance_heats_up_when_open(fridge_fixture):
    open_fridge = deepcopy(fridge_fixture)
    open_fridge.trigger_open()
    open_fridge.event_activate()
    fridge_fixture.event_activate()
    fridge_fixture.report_energy(0)
    open_fridge.report_energy(0)
    assert open_fridge.temperature + open_fridge.temp_change \
        > fridge_fixture.temperature + fridge_fixture.temp_change


# always buys energy if we have none and upper temperature constraint is violated

# @pytest.mark.skip("broken since appliance remodelling, needs to be rewritten")  # TODO FIX
def test_fridge_appliance_report_energy_too_warm(fridge_fixture):
    fridge_fixture.state.temperature = MAX_FRIDGE_TEMP + 1
    fridge_fixture.report_energy(0)
    assert fridge_fixture.area.reported_value < 0


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
