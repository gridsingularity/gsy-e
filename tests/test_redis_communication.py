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
from parameterized import parameterized
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
from d3a.models.area.event_dispatcher import RedisAreaDispatcher, AreaDispatcher
from d3a.models.area.redis_dispatcher.redis_communicator import RedisAreaCommunicator
from d3a.events.event_structures import AreaEvent, MarketEvent

log = getLogger(__name__)


mock_redis = MagicMock(spec=RedisAreaCommunicator)
mock_redis_market = MagicMock(spec=RedisAreaCommunicator)
mock_redis.area_event = MagicMock(spec=Event)


class MockDispatcherFactory:
    def __init__(self, area):
        self.event_dispatching_via_redis = \
            ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS
        self.dispatcher = RedisAreaDispatcher(area, mock_redis, mock_redis_market) \
            if self.event_dispatching_via_redis else AreaDispatcher(area)

    def __call__(self):
        return self.dispatcher


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
        ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS = False

    def test_subscribe(self):
        mock_redis.sub_to_area_event.assert_any_call(
            f"storage/area_event",
            self.device2.dispatcher.area_event_dispatcher.event_listener_redis)
        mock_redis.sub_to_area_event.assert_any_call(
            f"load/area_event",
            self.device1.dispatcher.area_event_dispatcher.event_listener_redis)
        mock_redis.sub_to_area_event.assert_any_call(
            f"area/area_event",
            self.area.dispatcher.area_event_dispatcher.event_listener_redis)
        mock_redis.sub_to_response.assert_any_call(
            f"storage/area_event_response",
            self.device2.dispatcher.area_event_dispatcher.response_callback)
        mock_redis.sub_to_response.assert_any_call(
            f"load/area_event_response",
            self.device1.dispatcher.area_event_dispatcher.response_callback)
        mock_redis.sub_to_response.assert_any_call(
            f"area/area_event_response",
            self.area.dispatcher.area_event_dispatcher.response_callback)

    def tests_broadcast(self):
        for area_event in [AreaEvent.TICK, AreaEvent.MARKET_CYCLE, AreaEvent.ACTIVATE,
                           AreaEvent.BALANCING_MARKET_CYCLE]:
            self.area.dispatcher.broadcast_callback(area_event)
            for child in self.area.children:
                dispatch_chanel = f"{child.slug}/area_event"
                send_data = json.dumps({"event_type": area_event.value, "kwargs": {}})
                mock_redis.publish.assert_any_call(dispatch_chanel, send_data)
                mock_redis.wait.assert_called()

    def test_receive(self):

        for area_event in [AreaEvent.TICK, AreaEvent.MARKET_CYCLE, AreaEvent.ACTIVATE,
                           AreaEvent.BALANCING_MARKET_CYCLE]:
            payload = {"data": json.dumps({"event_type": area_event.value, "kwargs": {}})}
            self.device1.dispatcher.area_event_dispatcher.event_listener_redis(payload)
            response_channel = f"{self.area.slug}/area_event_response"
            response_data = json.dumps({"response": area_event.name.lower()})
            mock_redis.publish.assert_any_call(response_channel, response_data)

    def test_response_callback(self):
        for area_event in [AreaEvent.TICK, AreaEvent.MARKET_CYCLE, AreaEvent.ACTIVATE,
                           AreaEvent.BALANCING_MARKET_CYCLE]:
            payload = {"data": json.dumps({"response": area_event.name.lower()})}
            self.area.dispatcher.area_event_dispatcher.response_callback(payload)
            mock_redis.resume.assert_called()


class TestRedisMarketEventDispatcher(unittest.TestCase):

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
        self.area.dispatcher.market_event_dispatcher.redis = MagicMock(spec=RedisAreaCommunicator)
        self.device1.dispatcher.market_event_dispatcher.redis = MagicMock(
            spec=RedisAreaCommunicator)
        self.device2.dispatcher.market_event_dispatcher.redis = MagicMock(
            spec=RedisAreaCommunicator)
        self.area.dispatcher.market_event_dispatcher.active_trade = False
        self.device1.dispatcher.market_event_dispatcher.active_trade = False
        self.device2.dispatcher.market_event_dispatcher.active_trade = False
        self.area.dispatcher.market_event_dispatcher.deferred_events = []
        self.device1.dispatcher.market_event_dispatcher.deferred_events = []
        self.device2.dispatcher.market_event_dispatcher.deferred_events = []

    def tearDown(self):
        ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS = False

    def test_subscribe(self):
        mock_redis_market.sub_to_area_event.assert_any_call(
            f"storage/market_event",
            self.device2.dispatcher.market_event_dispatcher.event_listener_redis)
        mock_redis_market.sub_to_area_event.assert_any_call(
            f"load/market_event",
            self.device1.dispatcher.market_event_dispatcher.event_listener_redis)
        mock_redis_market.sub_to_area_event.assert_any_call(
            f"area/market_event",
            self.area.dispatcher.market_event_dispatcher.event_listener_redis)
        mock_redis_market.sub_to_response.assert_any_call(
            f"storage/market_event_response",
            self.device2.dispatcher.market_event_dispatcher.response_callback)
        mock_redis_market.sub_to_response.assert_any_call(
            f"load/market_event_response",
            self.device1.dispatcher.market_event_dispatcher.response_callback)
        mock_redis_market.sub_to_response.assert_any_call(
            f"area/market_event_response",
            self.area.dispatcher.market_event_dispatcher.response_callback)

    @parameterized.expand([(MarketEvent.OFFER_CHANGED, ), (MarketEvent.TRADE, ),
                           (MarketEvent.BID_TRADED, ), (MarketEvent.BID_CHANGED, )])
    def tests_broadcast_trade_related_events_should_wait(self, market_event):
        self.area.dispatcher.broadcast_callback(market_event)
        for child in self.area.children:
            dispatch_chanel = f"{child.slug}/market_event"
            send_data = json.dumps({"event_type": market_event.value, "kwargs": {}})
            self.area.dispatcher.market_event_dispatcher.redis.publish.assert_any_call(
                dispatch_chanel, send_data)
            self.area.dispatcher.market_event_dispatcher.redis.wait.assert_called()

    @parameterized.expand([(MarketEvent.BID_DELETED, ), (MarketEvent.OFFER, ),
                           (MarketEvent.OFFER_DELETED, )])
    def tests_broadcast_non_trade_related_events_should_not_wait(self, market_event):
        self.area.dispatcher.broadcast_callback(market_event)
        for child in self.area.children:
            dispatch_chanel = f"{child.slug}/market_event"
            send_data = json.dumps({"event_type": market_event.value, "kwargs": {}})
            self.area.dispatcher.market_event_dispatcher.redis.publish.assert_any_call(
                dispatch_chanel, send_data)
            self.area.dispatcher.market_event_dispatcher.redis.wait.assert_not_called()

    @parameterized.expand([(MarketEvent.OFFER_CHANGED, ), (MarketEvent.BID_CHANGED, )])
    def tests_broadcast_offer_bid_change_events_set_active_trade_flag(self, market_event):
        # Setting the flag to false before the broadcast, to ensure that the flag is changed
        # to true
        self.area.dispatcher.market_event_dispatcher.active_trade = False
        self.area.dispatcher.broadcast_callback(market_event)
        assert self.area.dispatcher.market_event_dispatcher.active_trade is True

    @parameterized.expand([(MarketEvent.TRADE, ), (MarketEvent.BID_TRADED, )])
    def tests_broadcast_trade_events_unset_active_trade_flag(self, market_event):
        # Setting the flag to true before the broadcast, to ensure that the flag is changed
        # to false
        self.area.dispatcher.market_event_dispatcher.active_trade = True
        self.area.dispatcher.broadcast_callback(market_event)
        assert self.area.dispatcher.market_event_dispatcher.active_trade is False

    @parameterized.expand([(MarketEvent.BID_TRADED, ), (MarketEvent.BID_CHANGED, ),
                           (MarketEvent.OFFER_CHANGED, ), (MarketEvent.TRADE, )])
    def test_receive_publishes_trade_related_events_immediately(self, market_event):
        payload = {"data": json.dumps({"event_type": market_event.value, "kwargs": {}})}
        assert len(self.device1.dispatcher.market_event_dispatcher.deferred_events) == 0
        self.device1.dispatcher.market_event_dispatcher.event_listener_redis(payload)
        response_channel = f"{self.area.slug}/market_event_response"
        response_data = json.dumps({"response": market_event.name.lower()})
        self.device1.dispatcher.market_event_dispatcher.redis.publish.assert_any_call(
            response_channel, response_data)
        assert len(self.device1.dispatcher.market_event_dispatcher.deferred_events) == 0

    @parameterized.expand([(MarketEvent.BID_DELETED, ), (MarketEvent.OFFER, ),
                           (MarketEvent.OFFER_DELETED, )])
    def test_receive_stores_non_trade_events_if_there_is_a_pending_trade(self, market_event):
        payload = {"data": json.dumps({"event_type": market_event.value, "kwargs": {}})}
        assert len(self.device1.dispatcher.market_event_dispatcher.deferred_events) == 0
        self.device1.dispatcher.market_event_dispatcher.active_trade = True
        self.device1.dispatcher.market_event_dispatcher.event_listener_redis(payload)
        self.device1.dispatcher.market_event_dispatcher.redis.publish.assert_not_called()
        assert len(self.device1.dispatcher.market_event_dispatcher.deferred_events) == 1
        serialized_event = self.device1.dispatcher.market_event_dispatcher.deferred_events[0]
        event_json = json.loads(serialized_event["data"])
        assert event_json["event_type"] == market_event.value
        assert self.device1.dispatcher.market_event_dispatcher.active_trade is True

    @parameterized.expand([(MarketEvent.BID_DELETED, ), (MarketEvent.OFFER, ),
                           (MarketEvent.OFFER_DELETED, )])
    def test_receive_publishes_all_stored_events_if_trade_event_has_completed(self, market_event):
        payload = {"data": json.dumps({"event_type": market_event.value, "kwargs": {}})}
        self.device1.dispatcher.market_event_dispatcher.deferred_events = [
            {"data": '{"event_type": 1, "kwargs": {}}'}
        ]
        self.device1.dispatcher.market_event_dispatcher.active_trade = False
        self.device1.dispatcher.market_event_dispatcher.event_listener_redis(payload)
        response_channel = f"{self.area.slug}/market_event_response"
        response_data = json.dumps({"response": market_event.name.lower()})
        self.device1.dispatcher.market_event_dispatcher.redis.publish.assert_any_call(
            response_channel, response_data)
        response_channel = f"{self.area.slug}/market_event_response"
        response_data = json.dumps({"response": 'offer'})
        self.device1.dispatcher.market_event_dispatcher.redis.publish.assert_any_call(
            response_channel, response_data)
        assert len(self.device1.dispatcher.market_event_dispatcher.deferred_events) == 0

    def test_response_callback(self):
        for area_event in [AreaEvent.TICK, AreaEvent.MARKET_CYCLE, AreaEvent.ACTIVATE,
                           AreaEvent.BALANCING_MARKET_CYCLE]:
            payload = {"data": json.dumps({"response": area_event.name.lower()})}
            self.area.dispatcher.area_event_dispatcher.response_callback(payload)
            mock_redis.resume.assert_called()
