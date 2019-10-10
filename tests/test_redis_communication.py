"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import unittest
import json
from logging import getLogger
from unittest.mock import MagicMock
from threading import Event

import d3a.models.area
from d3a.models.area import Area
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from d3a.models.area.event_dispatcher import RedisAreaDispatcher, AreaDispatcher, \
    RedisAreaCommunicator
from d3a.events.event_structures import AreaEvent

log = getLogger(__name__)


class MockDispatcherFactory:
    def __init__(self, area):
        self.event_dispatching_via_redis = \
            ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS
        self.dispatcher = RedisAreaDispatcher(area, mock_redis) \
            if self.event_dispatching_via_redis else AreaDispatcher(area)

    def __call__(self):
        return self.dispatcher


mock_redis = MagicMock(spec=RedisAreaCommunicator)
mock_redis.area_event = MagicMock(spec=Event)
d3a.models.area.DispatcherFactory = MockDispatcherFactory


class TestRedisEventDispatching(unittest.TestCase):

    def setUp(self):
        ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS = True
        self.appliance = MagicMock(spec=SimpleAppliance)
        self.load_strategy = MagicMock(spec=LoadHoursStrategy)
        self.storage_strategy = MagicMock(spec=StorageStrategy)
        self.config = MagicMock(spec=GlobalConfig)
        self.device1 = Area(name="Load", config=self.config, strategy=self.load_strategy,
                            appliance=self.appliance)
        self.device2 = Area(name="Storage", config=self.config, strategy=self.storage_strategy,
                            appliance=self.appliance)
        self.area = Area(name="Area", config=self.config,
                         children=[self.device1, self.device2])

    def tearDown(self):
        pass

    def test_subscribe(self):
        mock_redis.sub_to_area_event.assert_any_call(f"storage/area_event",
                                                     self.device2.dispatcher.event_listener_redis)
        mock_redis.sub_to_area_event.assert_any_call(f"load/area_event",
                                                     self.device1.dispatcher.event_listener_redis)
        mock_redis.sub_to_area_event.assert_any_call(f"area/area_event",
                                                     self.area.dispatcher.event_listener_redis)
        mock_redis.sub_to_response.assert_any_call(f"storage/area_event_response",
                                                   self.device2.dispatcher.response_callback)
        mock_redis.sub_to_response.assert_any_call(f"load/area_event_response",
                                                   self.device1.dispatcher.response_callback)
        mock_redis.sub_to_response.assert_any_call(f"area/area_event_response",
                                                   self.area.dispatcher.response_callback)

    def tests_broadcast(self):
        for area_event in [AreaEvent.TICK, AreaEvent.MARKET_CYCLE, AreaEvent.ACTIVATE,
                           AreaEvent.BALANCING_MARKET_CYCLE]:
            self.area.dispatcher._broadcast_event_redis(area_event)
            for child in self.area.children:
                dispatch_chanel = f"{child.slug}/area_event"
                send_data = json.dumps({"event_type": area_event.value, "kwargs": {}})
                mock_redis.publish.assert_any_call(dispatch_chanel, send_data)
                mock_redis.wait.assert_called()

    def test_receive(self):

        for area_event in [AreaEvent.TICK, AreaEvent.MARKET_CYCLE, AreaEvent.ACTIVATE,
                           AreaEvent.BALANCING_MARKET_CYCLE]:
            payload = {"data": json.dumps({"event_type": area_event.value, "kwargs": {}})}
            self.device1.dispatcher.event_listener_redis(payload)
            response_channel = f"{self.area.slug}/area_event_response"
            response_data = json.dumps({"response": area_event.name.lower()})
            mock_redis.publish.assert_any_call(response_channel, response_data)

    def test_response_callback(self):
        for area_event in [AreaEvent.TICK, AreaEvent.MARKET_CYCLE, AreaEvent.ACTIVATE,
                           AreaEvent.BALANCING_MARKET_CYCLE]:
            payload = {"data": json.dumps({"response": area_event.name.lower()})}
            self.area.dispatcher.response_callback(payload)
            mock_redis.resume.assert_called()
