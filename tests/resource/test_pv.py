from d3a.models.appliance.builder import gen_pv_appliance
from d3a.models.appliance.appliance import ApplianceMode
from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.properties import MeasurementParamType
from pendulum.interval import Interval
from time import sleep
import pendulum
import pytest


def get_pv_object():
    pv = gen_pv_appliance()
    return pv


def test_pv_creation():
    pv = gen_pv_appliance()
    assert pv is not None
    assert isinstance(pv, PVAppliance)


def test_pv_usage_curve():
    pv = get_pv_object()
    on_curve = pv.energyCurve.get_mode_curve(ApplianceMode.ON)
    assert len(on_curve) == 24*60*60    # take samples per sec for 24 hours.


def test_pv_mode_change():
    pv = get_pv_object()
    time_secs = Interval(hours=12, minutes=0, seconds=0).in_seconds()    # At noon
    on = None

    # power generated at noon
    for i in range(0, time_secs):
        on = pv.iterator.__next__()

    pv.change_mode_of_operation(ApplianceMode.OFF)
    off = pv.iterator.__next__()

    # zero index based list
    assert on == pv.energyCurve.get_mode_curve(ApplianceMode.ON)[time_secs - 1]
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


@pytest.mark.xfail(reason="Area and strategy objects are injected at runtime")
def test_pv_get_usage_reading():
    pv = get_pv_object()
    reading = pv.get_usage_reading()
    assert reading[0] == MeasurementParamType.POWER


@pytest.mark.xfail(reason="Area and strategy objects are injected at runtime")
def test_pv_partial_cloud_cover():
    pv = get_pv_object()
    cloud_cover_percent = 50
    cloud_cover_duration = 2
    cloud_cover_match = 0
    clear_sky_match = 0
    during_cloud_cover = dict()
    after_cloud_cover = dict()
    pv.handle_cloud_cover(cloud_cover_percent, cloud_cover_duration)

    for tick in range(0, cloud_cover_duration):
        pv.event_tick(area=None)
        during_cloud_cover[pendulum.now().diffcleart(pendulum.today()).in_seconds()] = \
            pv.get_current_power()
        sleep(1)

    for tick in range(0, cloud_cover_duration):
        pv.event_tick(area=None)
        after_cloud_cover[pendulum.now().diff(pendulum.today()).in_seconds()] = \
            pv.get_current_power()
        sleep(1)

    print("During cloud cover: {}".format(during_cloud_cover))
    print("After cloud cover: {}".format(after_cloud_cover))

    for key in during_cloud_cover.keys():
        print("During: {}, original: {}".
              format(during_cloud_cover[key], pv.usageGenerator.get_reading_at(key)))

        if during_cloud_cover[key] == \
            round(pv.usageGenerator.get_reading_at(key) *
                  (1 - cloud_cover_percent/100), 2):
            cloud_cover_match += 1

    for key in after_cloud_cover.keys():
        print("After: {}, original: {}".
              format(after_cloud_cover[key], pv.usageGenerator.get_reading_at(key)))
        if after_cloud_cover[key] == pv.usageGenerator.get_reading_at(key):
            clear_sky_match += 1

    assert clear_sky_match == cloud_cover_duration
    assert cloud_cover_match == cloud_cover_duration
