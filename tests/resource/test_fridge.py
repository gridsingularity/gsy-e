
from d3a.models.appliance.builder import gen_fridge_appliance
from d3a.models.appliance.appliance import ApplianceMode
from d3a.models.area import Area
from d3a.models.strategy.simple import BuyStrategy
from d3a.models.area import DEFAULT_CONFIG
import pytest


def get_fridge_object():
    fridge = gen_fridge_appliance()
    fridge.start_appliance()
    fridge.bids = [0.0028]  # , 0.0042, 0.0056, 0.0084, 0.0028, 0.0014, 0.0014, 0.0014]
    return fridge


def test_fridge_object():
    fridge = get_fridge_object()

    assert fridge is not None


def test_fridge_curves():
    fridge = get_fridge_object()
    on_curve = fridge.energy_curve.get_mode_curve(ApplianceMode.ON)
    off_curve = fridge.energy_curve.get_mode_curve(ApplianceMode.OFF)

    assert len(on_curve) == 5 * 60      # Fridge cooling cycle runs for 5 mins
    assert len(off_curve) == 2


@pytest.mark.xfail(reason="Area and strategy objects are injected at runtime")
def test_fridge_temp_rise_door_closed():
    """
    While the fridge is closed, temp of fridge rises if fridge is not cooling.
    """
    fridge = get_fridge_object()
    temp_change = []
    count = 0
    ticks = 100

    fridge.bids = [0.0028, 0.0042, 0.0056, 0.0084, 0.0028, 0.0014, 0.0014, 0.0014]
    fridge.event_market_cycle()
    strategy = BuyStrategy(buy_chance=1, max_energy=150)
    area = Area("Fridge Test", children=None, strategy=strategy, appliance=fridge, config=None)

    for i in range(0, ticks):
        area.tick()
        fridge.event_tick(area)
        temp_change.append(float(format(fridge.current_temp, '.4f')))

    for i in range(1, ticks):
        change = float(format(temp_change[i] - temp_change[i-1], '.4f'))
        print("Change: {}".format(change))
        if change == fridge.heating_per_tick:
            count += 1

    assert count == ticks - 1


@pytest.mark.xfail(reason="Area and strategy objects are injected at runtime")
def test_fridge_door_open():
    """
    Test to verify the fridge starts cooling if fridge door is opened long enough
    """
    fridge = get_fridge_object()
    fridge.current_temp = 5.0       # Set fridge temp to lowest
    door_open_for = 3               # Open door for 2 ticks
    before_temp = fridge.current_temp

    fridge.event_tick(area=None)
    fridge.event_tick(area=None)
    is_cooling_before_door_open = fridge.is_appliance_consuming_energy()
    is_cooling_after_door_open = False
    fridge.handle_door_open(door_open_for)

    for tick in range(0, 5):
        fridge.event_tick(area=None)

    is_cooling_after_door_open = fridge.is_appliance_consuming_energy()
    after_temp = fridge.current_temp

    print("Before temp: {}, after temp: {}".format(before_temp, after_temp))

    assert is_cooling_before_door_open is False
    assert is_cooling_after_door_open is True


@pytest.mark.xfail(reason="Area and strategy objects are injected at runtime")
def test_fridge_doesnt_cool_low_temp():
    fridge = get_fridge_object()
    fridge.current_temp = 8.0
    is_cooling = True
    run_for_ticks = DEFAULT_CONFIG.slot_length.in_seconds()

    for tick in range(0, run_for_ticks):
        fridge.event_tick(area=None)
        if tick == run_for_ticks - 1:
            is_cooling = fridge.is_appliance_consuming_energy()

    assert is_cooling is False


@pytest.mark.xfail(reason="Area and strategy objects are injected at runtime")
def test_fridge_temp_doesnt_exceed_max():
    fridge = get_fridge_object()
    fridge.current_temp = 14.0
    before_temp = fridge.current_temp
    after_temp = before_temp
    ticks_to_run = DEFAULT_CONFIG.slot_length.in_seconds()

    for tick in range(0, ticks_to_run):
        fridge.event_tick(area=None)

    after_temp = fridge.current_temp

    assert round(after_temp, 4) < round(before_temp, 4)


@pytest.mark.xfail(reason="Area and strategy objects are injected at runtime")
def test_fridge_temp_doesnt_fall_below_min():
    fridge = get_fridge_object()
    fridge.current_temp = 6.0
    before_temp = fridge.current_temp
    after_temp = before_temp
    ticks_to_run = DEFAULT_CONFIG.slot_length.in_seconds()

    for tick in range(0, ticks_to_run):
        fridge.event_tick(area=None)

    after_temp = fridge.current_temp

    assert round(after_temp, 4) > round(before_temp, 4)
