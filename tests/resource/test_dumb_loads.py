from d3a.models.resource.appliance import ApplianceMode, DumbLoad
from d3a.models.resource.builder import gen_light_bulb
from d3a.models.area import Area


def get_bulb_object():
    bulb = gen_light_bulb()
    bulb.start_appliance()

    return bulb


def test_bulb_toggle():
    bulb = get_bulb_object()
    mode_before_toggle = bulb.mode
    bulb.toggle_appliance()
    mode_after_toggle = bulb.mode

    assert mode_after_toggle is not mode_before_toggle


def test_power_on_bulb():
    bulb = get_bulb_object()
    bulb.power_on_appliance()
    trials = 100
    count = 0

    for tick in range(0, trials):
        bulb.event_tick(area=None)
        if bulb.get_current_power() >= 5.5:
            count += 1

    assert count == trials


def test_power_off_bulb():
    bulb = get_bulb_object()
    bulb.power_off_appliance()
    trials = 100
    count = 0

    for tick in range(0, trials):
        bulb.event_tick(area=None)
        if bulb.get_current_power() == 0:
            count += 1

    assert count == trials
