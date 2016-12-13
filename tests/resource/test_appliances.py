from d3a.models.resource.builder import gen_pv_appliance
from d3a.models.resource.appliance import PVAppliance, ApplianceMode
from d3a.models.resource.properties import MeasurementParamType


def get_pv_object():
    pv = gen_pv_appliance()
    pv.start_appliance()
    return pv


def test_pv_creation():
    pv = None
    pv = gen_pv_appliance()
    assert pv is not None
    assert isinstance(pv, PVAppliance)


def test_pv_usage_curve():
    pv = get_pv_object()
    on_curve = pv.energyCurve.get_mode_curve(ApplianceMode.ON)
    off_curve = pv.energyCurve.get_mode_curve(ApplianceMode.OFF)
    assert len(on_curve) == 1000
    assert len(off_curve) == 2


def test_pv_mode_change():
    pv = get_pv_object()
    on = pv.iterator.__next__()
    pv.change_mode_of_operation(ApplianceMode.OFF)
    off = pv.iterator.__next__()
    # PV in on mode can produce power between 265 - 300 W
    assert on > 265

    # During off state PV can produce power between -5 - +5 W
    assert int(off) >= -5 & int(off) <= 5


def test_pv_on_iterator():
    pv = get_pv_object()
    trials = 2000
    count = 0
    for a in range(0, trials):
        if pv.iterator.__next__() > 0:
            count += 1
    assert count == trials


def test_pv_off_iterator():
    pv = get_pv_object()
    trials = 500
    count = 0
    for a in range(0, trials):
        if pv.iterator.__next__() > 0:
            count += 1
    assert count == trials


def test_pv_get_usage_reading():
    pv = get_pv_object()
    reading = pv.get_usage_reading()
    assert reading[0] == MeasurementParamType.POWER


def test_historic_data_saved():
    pv = get_pv_object()
    iterations = 1000
    for i in range(0, iterations):
        pv.tick()

    assert len(pv.get_historic_usage_curve()) == iterations


