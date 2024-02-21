"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
# pylint: disable=missing-function-docstring, protected-access
from unittest.mock import MagicMock, Mock, call, patch

import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.enums import AvailableMarketTypes, BidOfferMatchAlgoEnum, SpotMarketTypeEnum
from pendulum import duration, today

from gsy_e import constants
from gsy_e.events.event_structures import AreaEvent, MarketEvent
from gsy_e.gsy_e_core.device_registry import DeviceRegistry
from gsy_e.models.area import Area, Asset, Market, check_area_name_exists_in_parent_area
from gsy_e.models.area.events import Events
from gsy_e.models.config import SimulationConfig
from gsy_e.models.strategy.storage import StorageStrategy


class TestArea:
    """Test the Area class behavior and state controllers."""

    @staticmethod
    @pytest.fixture(name="config")
    def config_fixture():
        """Instantiate a mocked configuration."""
        config = MagicMock(spec=SimulationConfig)
        config.slot_length = duration(minutes=15)
        config.tick_length = duration(seconds=15)
        config.ticks_per_slot = int(config.slot_length.seconds / config.tick_length.seconds)
        config.start_date = today(tz=constants.TIME_ZONE)
        config.sim_duration = duration(days=1)
        config.grid_fee_type = 1
        config.end_date = config.start_date + config.sim_duration

        return config

    @staticmethod
    def setup_method():
        GlobalConfig.sim_duration = duration(days=1)
        ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
        DeviceRegistry.REGISTRY = {
            "H1 General Load": (33, 35),
            "H2 General Load": (33, 35),
            "H1 Storage1": (23, 25),
            "H1 Storage2": (23, 25),
        }

    @staticmethod
    def teardown_method():
        ConstSettings.MASettings.MARKET_TYPE = SpotMarketTypeEnum.ONE_SIDED.value
        ConstSettings.MASettings.BID_OFFER_MATCH_TYPE = BidOfferMatchAlgoEnum.PAY_AS_BID.value
        ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS = False
        constants.RETAIN_PAST_MARKET_STRATEGIES_STATE = False

    @staticmethod
    def test_respective_area_grid_fee_is_applied(config):
        config.grid_fee_type = 2
        area = Area(name="Street", children=[Area(name="House")],
                    grid_fee_percentage=5, config=config)
        area.parent = Area(name="GRID", config=config)
        area.activate()
        assert area.spot_market.fee_class.grid_fee_rate == 0.05
        area.spot_market.offer(1, 1, "test", "test")
        assert list(area.spot_market.offers.values())[0].price == 1.05

    @staticmethod
    def test_delete_past_markets_instead_of_last(config):
        constants.RETAIN_PAST_MARKET_STRATEGIES_STATE = False
        area = Area(name="Street", children=[Area(name="House")],
                    config=config, grid_fee_percentage=5)
        area.activate()
        area._bc = None

        area.cycle_markets(False, False, False)
        assert len(area.past_markets) == 0

        current_time = today(tz=constants.TIME_ZONE).add(minutes=config.slot_length.minutes)
        area._markets.rotate_markets(current_time)
        assert len(area.past_markets) == 1

        area._markets.create_new_spot_market(
            current_time, AvailableMarketTypes.SPOT, area)
        current_time = today(tz=constants.TIME_ZONE).add(minutes=2 * config.slot_length.minutes)
        area._markets.rotate_markets(current_time)
        assert len(area.past_markets) == 1
        assert (list(area.past_markets)[-1].time_slot ==
                today(tz=constants.TIME_ZONE).add(minutes=config.slot_length.minutes))

    @staticmethod
    def test_keep_past_markets(config):
        constants.RETAIN_PAST_MARKET_STRATEGIES_STATE = True
        area = Area(name="Street", children=[Area(name="House")],
                    config=config, grid_fee_percentage=5)
        area.activate()
        area._bc = None

        area.cycle_markets(False, False, False)
        assert len(area.past_markets) == 0

        current_time = today(tz=constants.TIME_ZONE).add(
            minutes=config.slot_length.total_minutes())
        area._markets.rotate_markets(current_time)
        assert len(area.past_markets) == 1

        area._markets.create_new_spot_market(
            current_time, AvailableMarketTypes.SPOT, area)
        current_time = today(tz=constants.TIME_ZONE).add(
            minutes=2 * config.slot_length.total_minutes())
        area._markets.rotate_markets(current_time)
        assert len(area.past_markets) == 2

    @staticmethod
    def test_get_restore_state_get_called_on_all_areas():
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
        area.restore_state({"current_tick": 200})
        area.stats.restore_state.assert_called_once()
        assert area.current_tick == 200

        house.get_state()
        house.stats.get_state.assert_called_once()
        house.restore_state({"current_tick": 2432})
        house.stats.restore_state.assert_called_once()
        assert house.current_tick == 2432

        bat.get_state()
        strategy.get_state.assert_called_once()

    @staticmethod
    def test_get_state_returns_correct_values():
        # strategy = MagicMock(spec=StorageStrategy())
        bat = Area(name="battery", strategy=StorageStrategy())

        house = Area(name="House", children=[bat])
        assert house.get_state() == {"current_tick": 0,
                                     "exported_energy": {},
                                     "imported_energy": {},
                                     "rate_stats_market": {}}
        assert bat.get_state() == {"battery_energy_per_slot": 0.0,
                                   "charge_history": {},
                                   "charge_history_kWh": {},
                                   "current_tick": 0,
                                   "energy_to_buy_dict": {},
                                   "energy_to_sell_dict": {},
                                   "offered_buy_kWh": {},
                                   "offered_history": {},
                                   "offered_sell_kWh": {},
                                   "pledged_buy_kWh": {},
                                   "pledged_sell_kWh": {},
                                   "used_storage": 0.12}

    @staticmethod
    @patch("gsy_e.models.area.Area._consume_commands_from_aggregator", Mock())
    @patch("gsy_e.models.area.Area._update_matching_engine_matcher", Mock())
    @patch("gsy_e.models.area.area.bid_offer_matcher.match_recommendations")
    def test_tick(mock_match_recommendations, config):
        """Test the correct chain of function calls in the Area's tick function."""
        manager = Mock()
        strategy = MagicMock(spec=StorageStrategy)
        area = Area("test_area", None, None, strategy, config, None, grid_fee_percentage=1)
        area_child = Area("test_area_c", None, None, strategy, config, None, grid_fee_percentage=1)
        area_child.parent = area
        area.children = [area_child]
        area.grid_fee_percentage = 1

        manager.attach_mock(area._update_matching_engine_matcher, "update_matcher")
        manager.attach_mock(mock_match_recommendations, "match")

        ConstSettings.MASettings.MARKET_TYPE = SpotMarketTypeEnum.ONE_SIDED.value
        area.tick()
        assert manager.mock_calls == []

        # TWO Sided markets with internal matching, the order should be ->
        # consume commands from aggregator -> update matching engine cache
        # -> call matching engine clearing
        manager.reset_mock()
        ConstSettings.MASettings.MARKET_TYPE = SpotMarketTypeEnum.TWO_SIDED.value
        area.strategy = None
        area.tick()
        assert manager.mock_calls == [call.update_matcher(), call.match()]

        # TWO Sided markets with external matching, the order should be ->
        # call matching engine clearing -> consume commands from aggregator
        # -> update matching engine cache
        manager.reset_mock()
        ConstSettings.MASettings.BID_OFFER_MATCH_TYPE = BidOfferMatchAlgoEnum.EXTERNAL.value
        area.tick()
        assert manager.mock_calls == [call.match(), call.update_matcher()]


class TestEventDispatcher:
    """Test the dispatching of area events."""

    @staticmethod
    @pytest.fixture(name="strategy_mock")
    def strategy_fixture():
        strategy_mock = MagicMock()
        strategy_mock.event_listener = MagicMock()
        area = Area(name="test_area")
        area.strategy = strategy_mock
        area.events = MagicMock(spec=Events)

        return area

    @staticmethod
    def test_area_dispatches_activate_to_strategies_despite_connect_enable():
        area = Area(name="test_area")
        area.events = MagicMock(spec=Events)
        area.events.is_enabled = False
        area.events.is_connected = False
        assert area.dispatcher._should_dispatch_to_strategies(AreaEvent.ACTIVATE)
        area.events.is_enabled = True
        area.events.is_connected = True
        assert area.dispatcher._should_dispatch_to_strategies(AreaEvent.ACTIVATE)
        area.events.is_enabled = True
        area.events.is_connected = False
        assert area.dispatcher._should_dispatch_to_strategies(AreaEvent.ACTIVATE)
        area.events.is_enabled = False
        area.events.is_connected = True
        assert area.dispatcher._should_dispatch_to_strategies(AreaEvent.ACTIVATE)

    @staticmethod
    def test_are_dispatches_other_events_only_if_connected_and_enabled():
        area = Area(name="test_area")
        area.events = MagicMock(spec=Events)
        area.events.is_enabled = False
        area.events.is_connected = False
        assert not area.dispatcher._should_dispatch_to_strategies(AreaEvent.MARKET_CYCLE)

        area.events.is_enabled = True
        area.events.is_connected = False
        assert not area.dispatcher._should_dispatch_to_strategies(AreaEvent.MARKET_CYCLE)

        area.events.is_enabled = False
        area.events.is_connected = True
        assert not area.dispatcher._should_dispatch_to_strategies(AreaEvent.MARKET_CYCLE)

        area.events.is_enabled = True
        area.events.is_connected = True
        assert area.dispatcher._should_dispatch_to_strategies(AreaEvent.MARKET_CYCLE)

    @staticmethod
    @pytest.mark.parametrize("event_type, area_method", [
        (AreaEvent.MARKET_CYCLE, "cycle_markets"), (AreaEvent.ACTIVATE, "activate"),
        (AreaEvent.TICK, "tick")])
    def test_event_listener_calls_area_methods_for_area_events(event_type, area_method):
        function_mock = MagicMock(name=area_method)
        area = Area(name="test_area")
        setattr(area, area_method, function_mock)
        area.dispatcher.event_listener(event_type)
        assert function_mock.call_count == 1

    @staticmethod
    @pytest.mark.parametrize("event_type", [
        (MarketEvent.OFFER,),
        (MarketEvent.BID,),
        (MarketEvent.OFFER_TRADED,),
        (MarketEvent.OFFER_SPLIT,),
        (MarketEvent.BID_TRADED,),
        (MarketEvent.BID_DELETED,),
        (MarketEvent.OFFER_DELETED,)])
    def test_event_listener_dispatches_to_strategy_if_enabled_connected(event_type, strategy_mock):
        area = strategy_mock
        area.events.is_enabled = True
        area.events.is_connected = True
        area.dispatcher.event_listener(event_type)
        assert area.strategy.event_listener.call_count == 1

    @staticmethod
    @pytest.mark.parametrize("event_type", [
        (MarketEvent.OFFER,),
        (MarketEvent.BID,),
        (MarketEvent.OFFER_TRADED,),
        (MarketEvent.OFFER_SPLIT,),
        (MarketEvent.BID_TRADED,),
        (MarketEvent.BID_DELETED,),
        (MarketEvent.OFFER_DELETED,)])
    def test_event_listener_doesnt_dispatch_to_strategy_if_not_enabled(event_type, strategy_mock):
        area = strategy_mock
        area.events.is_enabled = False
        area.events.is_connected = True
        area.dispatcher.event_listener(event_type)
        assert area.strategy.event_listener.call_count == 0

    @staticmethod
    @pytest.mark.parametrize("event_type", [
        (MarketEvent.OFFER,),
        (MarketEvent.BID,),
        (MarketEvent.OFFER_TRADED,),
        (MarketEvent.OFFER_SPLIT,),
        (MarketEvent.BID_TRADED,),
        (MarketEvent.BID_DELETED,),
        (MarketEvent.OFFER_DELETED,)])
    def test_event_listener_doesnt_dispatch_to_strategy_if_not_connected(
            event_type, strategy_mock):
        area = strategy_mock
        area.events.is_enabled = True
        area.events.is_connected = False
        area.dispatcher.event_listener(event_type)
        assert area.strategy.event_listener.call_count == 0

    @staticmethod
    def test_event_on_disabled_area_triggered_for_market_cycle_on_disabled_area(strategy_mock):
        area = strategy_mock
        area.strategy.event_on_disabled_area = MagicMock()
        area.events.is_enabled = False
        area.events.is_connected = True
        area.dispatcher.event_listener(AreaEvent.MARKET_CYCLE)
        assert area.strategy.event_on_disabled_area.call_count == 1

    @staticmethod
    def test_duplicate_area_in_the_same_parent_append():
        area = Area(name="Street", children=[Area(name="House")], )
        with pytest.raises(Exception) as exception:
            area.children.append(Area(name="House", children=[Area(name="House")], ))
            assert exception == "Area name should be unique inside the same Parent Area"

    @staticmethod
    def test_duplicate_area_in_the_same_parent_change_name():
        child = Area(name="Street", )
        with pytest.raises(Exception) as exception:
            child.name = "Street 2"
            assert exception == "Area name should be unique inside the same Parent Area"


class TestFunctions:
    """Test utility functions in the area module."""

    @staticmethod
    def test_check_area_name_exists_in_parent_area():
        area = Area(name="Street", children=[Area(name="House")], )
        assert check_area_name_exists_in_parent_area(area, "House") is True
        assert check_area_name_exists_in_parent_area(area, "House 2") is False


class TestMarket:
    """Tests for the Market class."""

    @staticmethod
    def test_init_with_children():
        """The class can be correctly instantiated with children."""
        Market(name="Street", children=[Area(name="House")])


class TestAsset:
    """Tests for the Asset class."""

    @staticmethod
    def test_init_fails_with_children():
        """The class can't be initialized with children."""
        with pytest.raises(ValueError):
            Asset(name="Street", children=[Area(name="House")])

    @staticmethod
    def test_init_succeeds_without():
        """The class can be initialized without children."""
        Asset(name="Some device")
