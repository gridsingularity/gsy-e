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
from unittest.mock import MagicMock, patch, Mock, call

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.enums import SpotMarketTypeEnum, BidOfferMatchAlgoEnum
from parameterized import parameterized
from pendulum import duration, today

from d3a import constants
from d3a.d3a_core.device_registry import DeviceRegistry
from d3a.events.event_structures import AreaEvent, MarketEvent
from d3a.models.area import Area, check_area_name_exists_in_parent_area
from d3a.models.area.event_dispatcher import AreaDispatcher
from d3a.models.area.events import Events
from d3a.models.area.stats import AreaStats
from d3a.models.config import SimulationConfig
from d3a.models.market.market_structures import AvailableMarketTypes
from d3a.models.strategy.storage import StorageStrategy


class TestArea:
    """Test the Area class behavior and state controllers."""
    def setup_method(self):
        ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
        DeviceRegistry.REGISTRY = {
            "H1 General Load": (33, 35),
            "H2 General Load": (33, 35),
            "H1 Storage1": (23, 25),
            "H1 Storage2": (23, 25),
        }

        self.strategy = MagicMock(spec=StorageStrategy)
        self.config = MagicMock(spec=SimulationConfig)
        self.config.slot_length = duration(minutes=15)
        self.config.tick_length = duration(seconds=15)
        self.config.ticks_per_slot = int(self.config.slot_length.seconds /
                                         self.config.tick_length.seconds)
        self.config.start_date = today(tz=constants.TIME_ZONE)
        GlobalConfig.sim_duration = duration(days=1)
        self.config.sim_duration = duration(days=1)
        self.config.grid_fee_type = 1
        self.config.end_date = self.config.start_date + self.config.sim_duration
        self.area = Area("test_area", None, None, self.strategy,
                         self.config, None, grid_fee_percentage=1)
        self.area_child = Area("test_area_c", None, None, self.strategy,
                               self.config, None, grid_fee_percentage=1)
        self.area_child.parent = self.area
        self.area.children = [self.area_child]
        self.area.grid_fee_percentage = 1
        self.dispatcher = AreaDispatcher(self.area)
        self.stats = AreaStats(self.area._markets, self.area)

    def teardown_method(self):
        ConstSettings.IAASettings.MARKET_TYPE = SpotMarketTypeEnum.ONE_SIDED.value
        ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE = BidOfferMatchAlgoEnum.PAY_AS_BID.value
        ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS = False
        constants.RETAIN_PAST_MARKET_STRATEGIES_STATE = False

    def test_respective_area_grid_fee_is_applied(self):
        self.config.grid_fee_type = 2
        self.area = Area(name="Street", children=[Area(name="House")],
                         grid_fee_percentage=5, config=self.config)
        self.area.parent = Area(name="GRID", config=self.config)
        self.area.activate()
        assert self.area.spot_market.fee_class.grid_fee_rate == 0.05
        self.area.spot_market.offer(1, 1, "test", "test")
        assert list(self.area.spot_market.offers.values())[0].price == 1.05

    def test_delete_past_markets_instead_of_last(self):
        constants.RETAIN_PAST_MARKET_STRATEGIES_STATE = False
        self.area = Area(name="Street", children=[Area(name="House")],
                         config=self.config, grid_fee_percentage=5)
        self.area.activate()
        self.area._bc = None

        self.area.cycle_markets(False, False, False)
        assert len(self.area.past_markets) == 0

        current_time = today(tz=constants.TIME_ZONE).add(minutes=self.config.slot_length.minutes)
        self.area._markets.rotate_markets(current_time)
        assert len(self.area.past_markets) == 1

        self.area._markets.create_new_spot_market(
            current_time, AvailableMarketTypes.SPOT, self.area)
        current_time = today(tz=constants.TIME_ZONE).add(minutes=2*self.config.slot_length.minutes)
        self.area._markets.rotate_markets(current_time)
        assert len(self.area.past_markets) == 1
        assert (list(self.area.past_markets)[-1].time_slot ==
                today(tz=constants.TIME_ZONE).add(minutes=self.config.slot_length.minutes))

    def test_keep_past_markets(self):
        constants.RETAIN_PAST_MARKET_STRATEGIES_STATE = True
        self.area = Area(name="Street", children=[Area(name="House")],
                         config=self.config, grid_fee_percentage=5)
        self.area.activate()
        self.area._bc = None

        self.area.cycle_markets(False, False, False)
        assert len(self.area.past_markets) == 0

        current_time = today(tz=constants.TIME_ZONE).add(
            minutes=self.config.slot_length.total_minutes())
        self.area._markets.rotate_markets(current_time)
        assert len(self.area.past_markets) == 1

        self.area._markets.create_new_spot_market(
            current_time, AvailableMarketTypes.SPOT, self.area)
        current_time = today(tz=constants.TIME_ZONE).add(
            minutes=2*self.config.slot_length.total_minutes())
        self.area._markets.rotate_markets(current_time)
        assert len(self.area.past_markets) == 2

    def test_get_restore_state_get_called_on_all_areas(self):
        strategy = MagicMock(spec=StorageStrategy)
        bat = Area(name="battery", strategy=strategy)

        house = Area(name="House", children=[bat])
        house.stats.get_state = MagicMock()
        house.stats.restore_state = MagicMock()
        area = Area(name="Street", children=[house])
        area.stats.get_state = MagicMock()
        area.stats.restore_state = MagicMock()
        area.parent = Area(name="GRID")

        area.get_state()
        area.stats.get_state.assert_called_once()
        area.restore_state({"current_tick": 200, "area_stats": None})
        area.stats.restore_state.assert_called_once()
        assert area.current_tick == 200

        house.get_state()
        house.stats.get_state.assert_called_once()
        house.restore_state({"current_tick": 2432, "area_stats": None})
        house.stats.restore_state.assert_called_once()
        assert house.current_tick == 2432

        bat.get_state()
        strategy.get_state.assert_called_once()

    @patch("d3a.models.area.Area._consume_commands_from_aggregator", Mock())
    @patch("d3a.models.area.Area._update_myco_matcher", Mock())
    @patch("d3a.models.area.bid_offer_matcher.match_recommendations")
    def test_tick(self, mock_match_recommendations):
        """Test the correct chain of function calls in the Area's tick function."""
        manager = Mock()
        manager.attach_mock(self.area._consume_commands_from_aggregator, "consume_commands")
        manager.attach_mock(self.area._update_myco_matcher, "update_matcher")
        manager.attach_mock(mock_match_recommendations, "match")

        ConstSettings.IAASettings.MARKET_TYPE = SpotMarketTypeEnum.ONE_SIDED.value
        self.area.tick()
        assert manager.mock_calls == [call.consume_commands()]

        # TWO Sided markets with internal matching, the order should be ->
        # consume commands from aggregator -> update myco cache -> call myco clearing
        manager.reset_mock()
        ConstSettings.IAASettings.MARKET_TYPE = SpotMarketTypeEnum.TWO_SIDED.value
        self.area.strategy = None
        self.area.tick()
        assert manager.mock_calls == [call.consume_commands(), call.update_matcher(), call.match()]

        # TWO Sided markets with external matching, the order should be ->
        # call myco clearing -> consume commands from aggregator -> update myco cache
        manager.reset_mock()
        ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE = BidOfferMatchAlgoEnum.EXTERNAL.value
        self.area.tick()
        assert manager.mock_calls == [call.match(), call.consume_commands(), call.update_matcher()]


class TestEventDispatcher(unittest.TestCase):

    def test_area_dispatches_activate_to_strategies_despite_connect_enable(self):
        self.area = Area(name="test_area")
        self.area.events = MagicMock(spec=Events)
        self.area.events.is_enabled = False
        self.area.events.is_connected = False
        assert self.area.dispatcher._should_dispatch_to_strategies(AreaEvent.ACTIVATE)
        self.area.events.is_enabled = True
        self.area.events.is_connected = True
        assert self.area.dispatcher._should_dispatch_to_strategies(AreaEvent.ACTIVATE)
        self.area.events.is_enabled = True
        self.area.events.is_connected = False
        assert self.area.dispatcher._should_dispatch_to_strategies(AreaEvent.ACTIVATE)
        self.area.events.is_enabled = False
        self.area.events.is_connected = True
        assert self.area.dispatcher._should_dispatch_to_strategies(AreaEvent.ACTIVATE)

    def test_are_dispatches_other_events_only_if_connected_and_enabled(self):
        self.area = Area(name="test_area")
        self.area.events = MagicMock(spec=Events)
        self.area.events.is_enabled = False
        self.area.events.is_connected = False
        assert not self.area.dispatcher._should_dispatch_to_strategies(
            AreaEvent.MARKET_CYCLE)
        self.area.events.is_enabled = True
        self.area.events.is_connected = False
        assert not self.area.dispatcher._should_dispatch_to_strategies(
            AreaEvent.MARKET_CYCLE)
        self.area.events.is_enabled = False
        self.area.events.is_connected = True
        assert not self.area.dispatcher._should_dispatch_to_strategies(
            AreaEvent.MARKET_CYCLE)
        self.area.events.is_enabled = True
        self.area.events.is_connected = True
        assert self.area.dispatcher._should_dispatch_to_strategies(
            AreaEvent.MARKET_CYCLE)

    @parameterized.expand([(AreaEvent.MARKET_CYCLE, "cycle_markets"),
                           (AreaEvent.ACTIVATE, "activate"),
                           (AreaEvent.TICK, "tick")])
    def test_event_listener_calls_area_methods_for_area_events(self, event_type, area_method):
        function_mock = MagicMock(name=area_method)
        area = Area(name="test_area")
        setattr(area, area_method, function_mock)
        area.dispatcher.event_listener(event_type)
        assert function_mock.call_count == 1

    def strategy_mock(self):
        strategy_mock = MagicMock()
        strategy_mock.event_listener = MagicMock()
        area = Area(name="test_area")
        area.strategy = strategy_mock
        area.events = MagicMock(spec=Events)
        return area

    @parameterized.expand([(MarketEvent.OFFER, ),
                           (MarketEvent.OFFER_TRADED,),
                           (MarketEvent.OFFER_SPLIT, ),
                           (MarketEvent.BID_TRADED, ),
                           (MarketEvent.BID_DELETED, ),
                           (MarketEvent.OFFER_DELETED, )])
    def test_event_listener_dispatches_to_strategy_if_enabled_connected(
            self, event_type
    ):
        area = self.strategy_mock()
        area.events.is_enabled = True
        area.events.is_connected = True
        area.dispatcher.event_listener(event_type)
        assert area.strategy.event_listener.call_count == 1

    @parameterized.expand([(MarketEvent.OFFER, ),
                           (MarketEvent.OFFER_TRADED,),
                           (MarketEvent.OFFER_SPLIT, ),
                           (MarketEvent.BID_TRADED, ),
                           (MarketEvent.BID_DELETED, ),
                           (MarketEvent.OFFER_DELETED, )])
    def test_event_listener_doesnt_dispatch_to_strategy_if_not_enabled(self, event_type):
        area = self.strategy_mock()
        area.events.is_enabled = False
        area.events.is_connected = True
        area.dispatcher.event_listener(event_type)
        assert area.strategy.event_listener.call_count == 0

    @parameterized.expand([(MarketEvent.OFFER, ),
                           (MarketEvent.OFFER_TRADED,),
                           (MarketEvent.OFFER_SPLIT, ),
                           (MarketEvent.BID_TRADED, ),
                           (MarketEvent.BID_DELETED, ),
                           (MarketEvent.OFFER_DELETED, )])
    def test_event_listener_doesnt_dispatch_to_strategy_if_not_connected(
            self, event_type
    ):
        area = self.strategy_mock()
        area.events.is_enabled = True
        area.events.is_connected = False
        area.dispatcher.event_listener(event_type)
        assert area.strategy.event_listener.call_count == 0

    def test_event_on_disabled_area_triggered_for_market_cycle_on_disabled_area(self):
        area = self.strategy_mock()
        area.strategy.event_on_disabled_area = MagicMock()
        area.events.is_enabled = False
        area.events.is_connected = True
        area.dispatcher.event_listener(AreaEvent.MARKET_CYCLE)
        assert area.strategy.event_on_disabled_area.call_count == 1

    def test_duplicate_area_in_the_same_parent_append(self):
        area = Area(name="Street", children=[Area(name="House")], )
        with self.assertRaises(Exception) as exception:
            area.children.append(Area(name="House", children=[Area(name="House")], ))
            self.assertEqual(exception, "Area name should be unique inside the same Parent Area")

    def test_duplicate_area_in_the_same_parent_change_name(self):
        child = Area(name="Street", )
        parent = Area(name="Community", children=[child, Area(name="Street 2")]) # noqa
        with self.assertRaises(Exception) as exception:
            child.name = "Street 2"
            self.assertEqual(exception, "Area name should be unique inside the same Parent Area")


class TestFunctions(unittest.TestCase):

    def test_check_area_name_exists_in_parent_area(self):
        area = Area(name="Street", children=[Area(name="House")], )
        self.assertTrue(check_area_name_exists_in_parent_area(area, "House"))
        self.assertFalse(check_area_name_exists_in_parent_area(area, "House 2"))
