import unittest
import pytest
import datetime
from d3a.models.area import Area
from d3a.models.area.event_deserializer import deserialize_events_to_areas
from d3a.models.area.event_types import DisconnectAreaEvent, ConnectAreaEvent, \
    DisableAreaEvent, EnableAreaEvent


class TestEventDeserializer(unittest.TestCase):

    def test_event_deserializing_works_for_area_events(self):
        events = {
            "area_events": [
                {"area_uuid": "uuid_one",
                 "trigger_events": [
                     {"time": 1562500000, "type": 1},
                     {"time": 1562800000, "type": 2}
                 ]
                 }
            ]
        }
        area = Area(name="testarea", uuid="uuid_one", children=[])
        deserialize_events_to_areas(events, area)
        assert not area.events.config_events
        assert len(area.events.connect_disconnect_events.isolated_ev.event_list) == 2
        assert type(area.events.connect_disconnect_events.isolated_ev.event_list[0]) == \
            DisconnectAreaEvent
        assert area.events.connect_disconnect_events.isolated_ev.event_list[0].event_time == \
            datetime.datetime.fromtimestamp(1562500000)
        assert type(area.events.connect_disconnect_events.isolated_ev.event_list[1]) == \
            ConnectAreaEvent
        assert area.events.connect_disconnect_events.isolated_ev.event_list[1].event_time == \
            datetime.datetime.fromtimestamp(1562800000)

    def test_deserialization_raises_exception_if_two_events_same_uuid(self):
        events = {
            "area_events": [
                {"area_uuid": "uuid_one",
                 "trigger_events": [
                     {"time": 1562500000, "type": 1},
                 ]
                 },
                {"area_uuid": "uuid_one",
                 "trigger_events": [
                     {"time": 1562600000, "type": 2},
                 ]
                 }
            ]
        }
        area = Area(name="testarea", uuid="uuid_one", children=[])
        with pytest.raises(ValueError):
            deserialize_events_to_areas(events, area)

    def test_deserialization_works_for_multiple_areas(self):
        events = {
            "area_events": [
                {"area_uuid": "uuid_one",
                 "trigger_events": [{"time": 1562500000, "type": 1}]},
                {"area_uuid": "uuid_two",
                 "trigger_events": [{"time": 1562800000, "type": 2}]},
                {"area_uuid": "uuid_three",
                 "trigger_events": [{"time": 1562840000, "type": 3}]},
                {"area_uuid": "uuid_four",
                 "trigger_events": [{"time": 1562856000, "type": 4}]}
            ]
        }
        child1 = Area(name="child1", uuid="uuid_two")
        child2 = Area(name="child2", uuid="uuid_three")
        child3 = Area(name="child3", uuid="uuid_four")
        area = Area(name="testarea", uuid="uuid_one", children=[
            child1, child2, child3
        ])
        deserialize_events_to_areas(events, area)
        assert len(area.events.connect_disconnect_events.isolated_ev.event_list) == 1
        assert type(area.events.connect_disconnect_events.isolated_ev.event_list[0]) == \
            DisconnectAreaEvent
        assert area.events.connect_disconnect_events.isolated_ev.event_list[0].event_time == \
            datetime.datetime.fromtimestamp(1562500000)

        assert len(child1.events.connect_disconnect_events.isolated_ev.event_list) == 1
        assert type(child1.events.connect_disconnect_events.isolated_ev.event_list[0]) == \
            ConnectAreaEvent
        assert child1.events.connect_disconnect_events.isolated_ev.event_list[0].event_time == \
            datetime.datetime.fromtimestamp(1562800000)

        assert len(child2.events.enable_disable_events.isolated_ev.event_list) == 1
        assert type(child2.events.enable_disable_events.isolated_ev.event_list[0]) == \
            DisableAreaEvent
        assert child2.events.enable_disable_events.isolated_ev.event_list[0].event_time == \
            datetime.datetime.fromtimestamp(1562840000)

        assert len(child3.events.enable_disable_events.isolated_ev.event_list) == 1
        assert type(child3.events.enable_disable_events.isolated_ev.event_list[0]) == \
            EnableAreaEvent
        assert child3.events.enable_disable_events.isolated_ev.event_list[0].event_time == \
            datetime.datetime.fromtimestamp(1562856000)

    def test_event_deserialization_works_for_setting_events(self):
        events = {
            "settings_events": [
                {"market_maker_rate": 123, "cloud_coverage": 1, "time": 1562856000},
                {"market_maker_rate_file": {"00:00": 123, "10:00": 43242},
                 "cloud_coverage": 2,
                 "time": 1562856789},
            ]
        }
        child1 = Area(name="child1", uuid="uuid_two")
        area = Area(name="testarea", uuid="uuid_one", children=[child1])
        deserialize_events_to_areas(events, area)
        assert len(area.events.config_events) == 2
        assert area.events.config_events[0].event_time == \
            datetime.datetime.fromtimestamp(1562856000)
        assert area.events.config_events[0].params == \
            {"market_maker_rate": 123, "cloud_coverage": 1,
             'pv_user_profile': None, 'transfer_fee_pct': None}
        assert area.events.config_events[1].event_time == \
            datetime.datetime.fromtimestamp(1562856789)
        assert area.events.config_events[1].params == \
            {"market_maker_rate": {"00:00": 123, "10:00": 43242}, "cloud_coverage": 2,
             'pv_user_profile': None, 'transfer_fee_pct': None}
