from d3a.models.resource.builder import gen_pv_appliance
from d3a.models.resource.appliance import PVAppliance, ApplianceMode
from d3a.models.resource.properties import MeasurementParamType
from pendulum.interval import Interval


def get_pv_object():
    pv = gen_pv_appliance()
    pv.start_appliance()
    return pv


def test_pv_creation():
    pv = gen_pv_appliance()
    assert pv is not None
    assert isinstance(pv, PVAppliance)


def test_pv_usage_curve():
    pv = get_pv_object()
    on_curve = pv.energyCurve.get_mode_curve(ApplianceMode.ON)
    off_curve = pv.energyCurve.get_mode_curve(ApplianceMode.OFF)
    assert len(on_curve) == 24*60*60    # take samples per sec for 24 hours.


def test_pv_mode_change():
    pv = get_pv_object()
    time_secs = Interval(hours=12, minutes=0, seconds=0).in_seconds()    # At noon

    # power generated at noon
    for i in range(0, time_secs):
        on = pv.iterator.__next__()

    pv.change_mode_of_operation(ApplianceMode.OFF)
    off = pv.iterator.__next__()

    assert on == pv.energyCurve.get_mode_curve(ApplianceMode.ON)[time_secs - 1]  # zero index based list
    assert int(off) == 0


def test_pv_on_iterator():
    pv = get_pv_object()
    noon = Interval(hours=12, minutes=0, seconds=0).in_seconds()
    after_an_hour = Interval(hours=13, minutes=0, seconds=0).in_seconds()
    count = 0
    for sec in range(noon, after_an_hour):
        if pv.usageGenerator.get_reading_at(sec) > 0:
            count += 1
    assert count == after_an_hour - noon


def test_pv_off_iterator():
    pv = get_pv_object()
    trials = 500
    count = 0
    for a in range(0, trials):
        if pv.iterator.__next__() == 0:
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
        pv.event_tick()

    # assert len(pv.get_historic_usage_curve()) == iterations
    assert not pv.get_historic_usage_curve()


# def test_pv_partial_cloud_cover():
#     pv = get_pv_object()
#     cloud_cover_duration = 5
#     pv.handle_cloud_cover(50, cloud_cover_duration)
#
#     for tick in range(0, cloud_cover_duration):
#         pv.event_tick()



