from copy import deepcopy
from collections import defaultdict

import pytest
from unittest.mock import MagicMock

from d3a.models.appliance.custom_profile import CustomProfileAppliance
from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import DEFAULT_CONFIG
from d3a.models.area.stats import AreaStats
from d3a.models.strategy.const import ConstSettings

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


class FakeFridgeState:
    def __init__(self):
        self.temperature = ConstSettings.FridgeSettings.TEMPERATURE
        self.max_temperature = ConstSettings.FridgeSettings.MAX_TEMP


class FakeFridgeStrategy:
    @property
    def fridge_temp(self):
        return self.temperature

    @property
    def state(self):
        return FakeFridgeState()

    def post(self, **data):
        pass


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

def test_fridge_appliance_report_energy_too_warm(fridge_fixture):
    fridge_fixture.state.temperature = ConstSettings.FridgeSettings.MAX_TEMP + 1
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


@pytest.fixture
def custom_profile_fixture(called):
    fixture = CustomProfileAppliance()
    fixture.area = FakeArea()
    fixture.owner = FakeOwnerWithStrategyAndMarket(FakeCustomProfileStrategy(33.0, 30.0))
    fixture.event_activate()
    fixture.log.warning = called
    return fixture


def test_custom_profile_appliance_lacking_energy_warning(custom_profile_fixture):
    custom_profile_fixture.owner.strategy.bought_val = 26.0
    custom_profile_fixture.event_market_cycle()
    assert len(custom_profile_fixture.log.warning.calls) == 1
