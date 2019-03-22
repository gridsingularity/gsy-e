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
from pendulum import duration, today
from collections import OrderedDict
from unittest.mock import MagicMock
import unittest
from parameterized import parameterized
from d3a.events.event_structures import AreaEvent, MarketEvent
from d3a.models.area import Area
from d3a.models.area.events import Events
from d3a.models.area.markets import AreaMarkets
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.config import SimulationConfig
from d3a.models.market import Market
from d3a.models.market.market_structures import Offer
from d3a.models.const import ConstSettings, GlobalConfig
from d3a.constants import TIME_ZONE
from d3a.d3a_core.device_registry import DeviceRegistry


class TestAreaClass(unittest.TestCase):

    def setUp(self):
        ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
        DeviceRegistry.REGISTRY = {
            "H1 General Load": (33, 35),
            "H2 General Load": (33, 35),
            "H1 Storage1": (23, 25),
            "H1 Storage2": (23, 25),
        }

        self.appliance = MagicMock(spec=SimpleAppliance)
        self.strategy = MagicMock(spec=StorageStrategy)
        self.config = MagicMock(spec=SimulationConfig)
        self.config.slot_length = duration(minutes=15)
        self.config.tick_length = duration(seconds=15)
        self.config.start_date = today(tz=TIME_ZONE)
        self.config.sim_duration = duration(days=1)
        self.area = Area("test_area", None, None, self.strategy,
                         self.appliance, self.config, None, transfer_fee_pct=1)
        self.area.parent = self.area
        self.area.children = [self.area]
        self.area.transfer_fee_pct = 1

    def tearDown(self):
        GlobalConfig.market_count = 1

    def test_respective_area_grid_fee_applied_for_offer(self):
        self.area = Area(name="Street", children=[Area(name="House")],
                         config=GlobalConfig, transfer_fee_pct=5)
        self.area.parent = Area(name="GRID")
        self.area.config.market_count = 1
        self.area.activate()
        self.area.next_market.offer(1, 1, "test", True)
        assert list(self.area.next_market.offers.values())[0].price == 1.05

    def test_markets_are_cycled_according_to_market_count(self):
        self.area._bc = False
        for i in range(2, 97):
            self.config.market_count = i
            self.area._cycle_markets(False, False)
            assert len(self.area.all_markets) == i

    def test_market_with_most_expensive_offer(self):
        m1 = MagicMock(spec=Market)
        o1 = MagicMock(spec=Offer)
        o1.price = 12
        o1.energy = 1
        m2 = MagicMock(spec=Market)
        o2 = MagicMock(spec=Offer)
        o2.price = 12
        o2.energy = 1
        m3 = MagicMock(spec=Market)
        o3 = MagicMock(spec=Offer)
        o3.price = 12
        o3.energy = 1
        markets = OrderedDict()
        td = today(tz=TIME_ZONE)
        td1 = td + self.config.slot_length
        m1.time_slot = td1
        markets[m1.time_slot] = m1
        td2 = td1 + self.config.slot_length
        m2.time_slot = td2
        markets[m2.time_slot] = m2
        td3 = td2 + self.config.slot_length
        m3.time_slot = td3
        markets[m3.time_slot] = m3
        self.area._markets = MagicMock(spec=AreaMarkets)
        self.area._markets.markets = markets
        m1.sorted_offers = [o1, o1]
        m2.sorted_offers = [o2, o2]
        m3.sorted_offers = [o3, o3]
        assert self.area.market_with_most_expensive_offer is m1
        o1.price = 19
        o2.price = 20
        o3.price = 18
        assert self.area.market_with_most_expensive_offer is m2
        o1.price = 18
        o2.price = 19
        o3.price = 20
        assert self.area.market_with_most_expensive_offer is m3

    def test_cycle_markets(self):
        self.area = Area(name="Street", children=[Area(name="House")],
                         config=GlobalConfig, transfer_fee_pct=1)
        self.area.parent = Area(name="GRID")
        self.area.config.market_count = 5
        self.area.activate()
        assert len(self.area.all_markets) == 5

        assert len(self.area.balancing_markets) == 5
        self.area.current_tick = 900
        self.area.tick(is_root_area=True)
        assert len(self.area.past_markets) == 1
        assert len(self.area.past_balancing_markets) == 1
        assert len(self.area.all_markets) == 5
        assert len(self.area.balancing_markets) == 5


class TestEventDispatcher(unittest.TestCase):

    def test_area_dispatches_activate_to_strategies_despite_connect_enable(self):
        self.area = Area(name="test_area")
        self.area.events = MagicMock(spec=Events)
        self.area.events.is_enabled = False
        self.area.events.is_connected = False
        assert self.area.dispatcher._should_dispatch_to_strategies_appliances(AreaEvent.ACTIVATE)
        self.area.events.is_enabled = True
        self.area.events.is_connected = True
        assert self.area.dispatcher._should_dispatch_to_strategies_appliances(AreaEvent.ACTIVATE)
        self.area.events.is_enabled = True
        self.area.events.is_connected = False
        assert self.area.dispatcher._should_dispatch_to_strategies_appliances(AreaEvent.ACTIVATE)
        self.area.events.is_enabled = False
        self.area.events.is_connected = True
        assert self.area.dispatcher._should_dispatch_to_strategies_appliances(AreaEvent.ACTIVATE)

    def test_are_dispatches_other_events_only_if_connected_and_enabled(self):
        self.area = Area(name="test_area")
        self.area.events = MagicMock(spec=Events)
        self.area.events.is_enabled = False
        self.area.events.is_connected = False
        assert not self.area.dispatcher._should_dispatch_to_strategies_appliances(
            AreaEvent.MARKET_CYCLE)
        self.area.events.is_enabled = True
        self.area.events.is_connected = False
        assert not self.area.dispatcher._should_dispatch_to_strategies_appliances(
            AreaEvent.MARKET_CYCLE)
        self.area.events.is_enabled = False
        self.area.events.is_connected = True
        assert not self.area.dispatcher._should_dispatch_to_strategies_appliances(
            AreaEvent.MARKET_CYCLE)
        self.area.events.is_enabled = True
        self.area.events.is_connected = True
        assert self.area.dispatcher._should_dispatch_to_strategies_appliances(
            AreaEvent.MARKET_CYCLE)

    @parameterized.expand([(AreaEvent.MARKET_CYCLE, "_cycle_markets"),
                           (AreaEvent.ACTIVATE, "activate"),
                           (AreaEvent.TICK, "tick")])
    def test_event_listener_calls_area_methods_for_area_events(self, event_type, area_method):
        function_mock = MagicMock(name=area_method)
        area = Area(name="test_area")
        setattr(area, area_method, function_mock)
        area.dispatcher.event_listener(event_type)
        assert function_mock.call_count == 1

    def strategy_appliance_mock(self):
        strategy_mock = MagicMock()
        strategy_mock.event_listener = MagicMock()
        appliance_mock = MagicMock()
        appliance_mock.event_listener = MagicMock()
        area = Area(name="test_area")
        area.strategy = strategy_mock
        area.appliance = appliance_mock
        area.events = MagicMock(spec=Events)
        return area

    @parameterized.expand([(MarketEvent.OFFER, ),
                           (MarketEvent.TRADE, ),
                           (MarketEvent.OFFER_CHANGED, ),
                           (MarketEvent.BID_TRADED, ),
                           (MarketEvent.BID_DELETED, ),
                           (MarketEvent.OFFER_DELETED, )])
    def test_event_listener_dispatches_to_strategy_appliance_if_enabled_connected(
            self, event_type
    ):
        area = self.strategy_appliance_mock()
        area.events.is_enabled = True
        area.events.is_connected = True
        area.dispatcher.event_listener(event_type)
        assert area.strategy.event_listener.call_count == 1
        assert area.appliance.event_listener.call_count == 1

    @parameterized.expand([(MarketEvent.OFFER, ),
                           (MarketEvent.TRADE, ),
                           (MarketEvent.OFFER_CHANGED, ),
                           (MarketEvent.BID_TRADED, ),
                           (MarketEvent.BID_DELETED, ),
                           (MarketEvent.OFFER_DELETED, )])
    def test_event_listener_doesnt_dispatch_to_strategy_appliance_if_not_enabled(self, event_type):
        area = self.strategy_appliance_mock()
        area.events.is_enabled = False
        area.events.is_connected = True
        area.dispatcher.event_listener(event_type)
        assert area.strategy.event_listener.call_count == 0
        assert area.appliance.event_listener.call_count == 0

    @parameterized.expand([(MarketEvent.OFFER, ),
                           (MarketEvent.TRADE, ),
                           (MarketEvent.OFFER_CHANGED, ),
                           (MarketEvent.BID_TRADED, ),
                           (MarketEvent.BID_DELETED, ),
                           (MarketEvent.OFFER_DELETED, )])
    def test_event_listener_doesnt_dispatch_to_strategy_appliance_if_not_connected(
            self, event_type
    ):
        area = self.strategy_appliance_mock()
        area.events.is_enabled = True
        area.events.is_connected = False
        area.dispatcher.event_listener(event_type)
        assert area.strategy.event_listener.call_count == 0
        assert area.appliance.event_listener.call_count == 0

    def test_event_on_disabled_area_triggered_for_market_cycle_on_disabled_area(self):
        area = self.strategy_appliance_mock()
        area.strategy.event_on_disabled_area = MagicMock()
        area.events.is_enabled = False
        area.events.is_connected = True
        area.dispatcher.event_listener(AreaEvent.MARKET_CYCLE)
        assert area.strategy.event_on_disabled_area.call_count == 1
