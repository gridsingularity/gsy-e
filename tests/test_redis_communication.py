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
from parameterized import parameterized
from logging import getLogger
from unittest.mock import MagicMock
from threading import Event
from pendulum import now

import d3a.models.area
from d3a.models.area import Area
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from d3a.models.area.event_dispatcher import RedisAreaDispatcher, AreaDispatcher
from d3a.d3a_core.redis_connections.redis_area_market_communicator import RedisCommunicator
from d3a.events.event_structures import AreaEvent, MarketEvent
from d3a.models.market.market_structures import Offer, Trade, offer_from_JSON_string, \
    trade_from_JSON_string

log = getLogger(__name__)


mock_redis = MagicMock(spec=RedisCommunicator)
mock_redis_market = MagicMock(spec=RedisCommunicator)
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
        mock_redis.sub_to_channel.assert_any_call(
            f"{self.device2.uuid}/area_event",
            self.device2.dispatcher.area_event_dispatcher.event_listener_redis)
        mock_redis.sub_to_channel.assert_any_call(
            f"{self.device1.uuid}/area_event",
            self.device1.dispatcher.area_event_dispatcher.event_listener_redis)
        mock_redis.sub_to_channel.assert_any_call(
            f"{self.area.uuid}/area_event",
            self.area.dispatcher.area_event_dispatcher.event_listener_redis)
        mock_redis.sub_to_response.assert_any_call(
            f"{self.device2.uuid}/area_event_response",
            self.device2.dispatcher.area_event_dispatcher.response_callback)
        mock_redis.sub_to_response.assert_any_call(
            f"{self.device1.uuid}/area_event_response",
            self.device1.dispatcher.area_event_dispatcher.response_callback)
        mock_redis.sub_to_response.assert_any_call(
            f"{self.area.uuid}/area_event_response",
            self.area.dispatcher.area_event_dispatcher.response_callback)

    @parameterized.expand([(AreaEvent.TICK, ),
                           (AreaEvent.MARKET_CYCLE, ),
                           (AreaEvent.ACTIVATE, ),
                           (AreaEvent.BALANCING_MARKET_CYCLE, )])
    def tests_broadcast(self, area_event):
        self.area.dispatcher.broadcast_callback(area_event)
        for child in self.area.children:
            dispatch_chanel = f"{child.uuid}/area_event"
            send_data = json.dumps({"event_type": area_event.value, "kwargs": {}})
            mock_redis.publish.assert_any_call(dispatch_chanel, send_data)
            mock_redis.wait.assert_called()

    @parameterized.expand([(AreaEvent.TICK, ),
                           (AreaEvent.MARKET_CYCLE, ),
                           (AreaEvent.ACTIVATE, ),
                           (AreaEvent.BALANCING_MARKET_CYCLE, )])
    def test_receive(self, area_event):
            payload = {"data": json.dumps({"event_type": area_event.value, "kwargs": {}})}
            self.device1.dispatcher.area_event_dispatcher.event_listener_redis(payload)
            response_channel = f"{self.area.uuid}/area_event_response"
            response_data = json.dumps({"response": area_event.name.lower()})
            mock_redis.publish.assert_any_call(response_channel, response_data)

    @parameterized.expand([(AreaEvent.TICK, ),
                           (AreaEvent.MARKET_CYCLE, ),
                           (AreaEvent.ACTIVATE, ),
                           (AreaEvent.BALANCING_MARKET_CYCLE, )])
    def test_response_callback(self, area_event):
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
        self.area.dispatcher.market_event_dispatcher.redis = MagicMock(spec=RedisCommunicator)
        self.area.dispatcher.market_event_dispatcher.child_response_events = {
            MarketEvent.TRADE.value: MagicMock(spec=Event),
            MarketEvent.OFFER.value: MagicMock(spec=Event),
            MarketEvent.OFFER_DELETED.value: MagicMock(spec=Event),
            MarketEvent.OFFER_CHANGED.value: MagicMock(spec=Event),
        }
        self.device1.dispatcher.market_event_dispatcher.redis = MagicMock(
            spec=RedisCommunicator)
        self.device1.dispatcher.market_event_dispatcher.child_response_events = {
            MarketEvent.TRADE.value: MagicMock(spec=Event),
            MarketEvent.OFFER.value: MagicMock(spec=Event),
            MarketEvent.OFFER_DELETED.value: MagicMock(spec=Event),
            MarketEvent.OFFER_CHANGED.value: MagicMock(spec=Event),
        }
        self.device2.dispatcher.market_event_dispatcher.redis = MagicMock(
            spec=RedisCommunicator)
        self.device2.dispatcher.market_event_dispatcher.child_response_events = {
            MarketEvent.TRADE.value: MagicMock(spec=Event),
            MarketEvent.OFFER.value: MagicMock(spec=Event),
            MarketEvent.OFFER_DELETED.value: MagicMock(spec=Event),
            MarketEvent.OFFER_CHANGED.value: MagicMock(spec=Event),
        }

    def tearDown(self):
        ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS = False

    def test_subscribe(self):
        mock_redis_market.sub_to_channel.assert_any_call(
            f"{self.device2.uuid}/market_event",
            self.device2.dispatcher.market_event_dispatcher.event_listener_redis)
        mock_redis_market.sub_to_channel.assert_any_call(
            f"{self.device1.uuid}/market_event",
            self.device1.dispatcher.market_event_dispatcher.event_listener_redis)
        mock_redis_market.sub_to_channel.assert_any_call(
            f"{self.area.uuid}/market_event",
            self.area.dispatcher.market_event_dispatcher.event_listener_redis)
        mock_redis_market.sub_to_response.assert_any_call(
            f"{self.device2.uuid}/market_event_response",
            self.device2.dispatcher.market_event_dispatcher.response_callback)
        mock_redis_market.sub_to_response.assert_any_call(
            f"{self.device1.uuid}/market_event_response",
            self.device1.dispatcher.market_event_dispatcher.response_callback)
        mock_redis_market.sub_to_response.assert_any_call(
            f"{self.area.uuid}/market_event_response",
            self.area.dispatcher.market_event_dispatcher.response_callback)

    @parameterized.expand([(MarketEvent.OFFER, ),
                           (MarketEvent.TRADE, ),
                           (MarketEvent.OFFER_CHANGED, ),
                           (MarketEvent.OFFER_DELETED, )])
    def test_publish_response(self, market_event):
        response_channel = f"{self.area.uuid}/market_event_response"
        response_payload = json.dumps({"response": market_event.name.lower(),
                                       "event_type": market_event.value})
        for dispatcher in [self.device1.dispatcher.market_event_dispatcher,
                           self.device2.dispatcher.market_event_dispatcher]:
            dispatcher.publish_response(market_event)
            dispatcher.redis.publish.assert_any_call(response_channel, response_payload)

    @parameterized.expand([(MarketEvent.OFFER, ),
                           (MarketEvent.TRADE, ),
                           (MarketEvent.OFFER_CHANGED, ),
                           (MarketEvent.OFFER_DELETED, )])
    def tests_broadcast(self, market_event):
        self.area.dispatcher.broadcast_callback(market_event)
        for child in self.area.children:
            dispatch_channel = f"{child.uuid}/market_event"
            send_data = json.dumps({"event_type": market_event.value, "kwargs": {}})
            market_dispatcher = self.area.dispatcher.market_event_dispatcher
            market_dispatcher.redis.publish.assert_any_call(
                dispatch_channel, send_data)
            assert market_dispatcher.child_response_events[market_event.value].\
                wait.call_count == len(self.area.children)
            assert market_dispatcher.child_response_events[market_event.value].\
                clear.call_count == len(self.area.children)

    @parameterized.expand([(MarketEvent.OFFER, ),
                           (MarketEvent.TRADE, ),
                           (MarketEvent.OFFER_CHANGED, ),
                           (MarketEvent.OFFER_DELETED, )])
    def test_response_callback_from_children_unblocks_thread_event(self, market_event):
        response_payload = {"data": json.dumps(
            {"response": market_event.name.lower(), "event_type": market_event.value}
        )}
        for dispatcher in [self.device1.dispatcher.market_event_dispatcher,
                           self.device2.dispatcher.market_event_dispatcher]:
            dispatcher.response_callback(response_payload)
            dispatcher.child_response_events[market_event.value].set.assert_called_once()

    def test_response_callback_from_children_raises_exception_for_wrong_event(self):
        response_payload = {"data": json.dumps(
            {"response": "wrong_event_type", "event_type": 1234124123}
        )}
        for dispatcher in [self.device1.dispatcher.market_event_dispatcher,
                           self.device2.dispatcher.market_event_dispatcher]:
            with self.assertRaises(Exception):
                dispatcher.response_callback(response_payload)
            for evt in dispatcher.child_response_events.values():
                evt.set.assert_not_called()

    @parameterized.expand([(MarketEvent.OFFER, ),
                           (MarketEvent.TRADE, ),
                           (MarketEvent.OFFER_CHANGED, ),
                           (MarketEvent.OFFER_DELETED, )])
    def test_event_listener_calls_the_event_listener_of_the_root_dispatcher(self, market_event):
        payload = {"data": json.dumps({"event_type": market_event.value, "kwargs": {}})}
        for dispatcher in [self.device1.dispatcher.market_event_dispatcher,
                           self.device2.dispatcher.market_event_dispatcher]:
            dispatcher.root_dispatcher.event_listener = MagicMock()
            dispatcher.event_listener_redis(payload)
            dispatcher.root_dispatcher.event_listener.assert_called_once_with(
                event_type=market_event)
            dispatcher.wait_for_futures()
            dispatcher.redis.publish.assert_called_once()

    def test_publish_event_converts_python_objects_to_json(self):
        offer = Offer("1", 2, 3, "A")
        trade = Trade("2", now(), Offer("accepted", 7, 8, "Z"), "B", "C")
        new_offer = Offer("3", 4, 5, "D")
        existing_offer = Offer("4", 5, 6, "E")
        kwargs = {"offer": offer,
                  "trade": trade,
                  "new_offer": new_offer,
                  "existing_offer": existing_offer}
        for dispatcher in [self.area.dispatcher.market_event_dispatcher,
                           self.device1.dispatcher.market_event_dispatcher,
                           self.device2.dispatcher.market_event_dispatcher]:
            dispatcher.publish_event(dispatcher.area.uuid, MarketEvent.OFFER, **kwargs)
            assert dispatcher.redis.publish.call_count == 1
            payload = json.loads(dispatcher.redis.publish.call_args_list[0][0][1])
            assert isinstance(payload["kwargs"]["offer"], str)
            assert offer_from_JSON_string(payload["kwargs"]["offer"]) == offer
            assert isinstance(payload["kwargs"]["trade"], str)
            assert trade_from_JSON_string(payload["kwargs"]["trade"]) == trade
            assert isinstance(payload["kwargs"]["new_offer"], str)
            assert offer_from_JSON_string(payload["kwargs"]["new_offer"]) == new_offer
            assert isinstance(payload["kwargs"]["existing_offer"], str)
            assert offer_from_JSON_string(payload["kwargs"]["existing_offer"]) == existing_offer
