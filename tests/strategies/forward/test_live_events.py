import itertools
from typing import Tuple, TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from gsy_framework.constants_limits import GlobalConfig, ConstSettings
from gsy_framework.enums import AvailableMarketTypes
from pendulum import datetime

from gsy_e.gsy_e_core.enums import FORWARD_MARKET_TYPES
from gsy_e.models.area import Area
from gsy_e.models.strategy.forward.load import ForwardLoadStrategy
from gsy_e.models.strategy.forward.pv import ForwardPVStrategy

if TYPE_CHECKING:
    from gsy_e.models.strategy.forward import ForwardStrategyBase

CURRENT_MARKET_SLOT = datetime(2022, 6, 13, 0, 0)


@pytest.fixture(name="forward_strategy_fixture", params=[ForwardLoadStrategy, ForwardPVStrategy])
def forward_market_strategy_fixture(request) -> Tuple["ForwardStrategyBase", "Area"]:
    """Fixture for the ForwardStrategy classes."""
    ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = True
    ConstSettings.ForwardMarketSettings.FULLY_AUTO_TRADING = False
    orig_start_date = GlobalConfig.start_date
    strategy = request.param(capacity_kW=100)
    strategy_area = Area("asset", strategy=strategy)
    area = Area("grid", children=[strategy_area])
    area.config.start_date = CURRENT_MARKET_SLOT
    area.config.end_date = area.config.start_date.add(years=20)
    # pylint: disable=protected-access
    strategy._energy_params.get_available_energy_kWh = MagicMock(return_value=100.0)
    yield strategy, area
    ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = False
    ConstSettings.ForwardMarketSettings.FULLY_AUTO_TRADING = True
    GlobalConfig.start_date = orig_start_date


@pytest.mark.slow
class TestForwardLiveEvents:
    # pylint: disable=protected-access

    @staticmethod
    def _assert_order_count_from_strategy(
            strategy: "ForwardStrategyBase", market_type: AvailableMarketTypes, order_count: int):
        if isinstance(strategy, ForwardPVStrategy):
            order_mapping = strategy.area.forward_markets[market_type].slot_offer_mapping
            order_list = strategy.area.forward_markets[market_type].get_offers()
        else:
            order_mapping = strategy.area.forward_markets[market_type].slot_bid_mapping
            order_list = strategy.area.forward_markets[market_type].get_bids()
        assert len(order_list) == order_count
        assert len(list(itertools.chain(*order_mapping.values()))) == order_count

    @staticmethod
    def test_no_orders_posted_without_live_events(forward_strategy_fixture):
        strategy = forward_strategy_fixture[0]
        area = forward_strategy_fixture[1]
        area.activate()
        # Trying 5 market cycles in order to validate that no order is posted.
        for _ in range(5):
            strategy.event_market_cycle()
            for market_type in FORWARD_MARKET_TYPES:
                market = area.forward_markets[market_type]
                assert len(market.get_bids()) == 0
                assert len(market.get_offers()) == 0

    @staticmethod
    @pytest.mark.parametrize("event_name", ["enable_trading", "post_order"])
    def test_enable_post_trading_event(forward_strategy_fixture, event_name):
        strategy = forward_strategy_fixture[0]
        area = forward_strategy_fixture[1]
        area.activate()
        strategy.event_market_cycle()
        strategy.apply_live_event({
            "type": event_name,
            "args": {
                "market_type": AvailableMarketTypes.INTRADAY.value,
                "start_time": "2022-06-13T00:00",
                "end_time": "2022-06-13T02:00",
                "capacity_percent": 20.0,
                "energy_rate": 30.0
            }})
        market = area.forward_markets[AvailableMarketTypes.INTRADAY]
        TestForwardLiveEvents._assert_order_count_from_strategy(
            strategy, AvailableMarketTypes.INTRADAY, 7)
        assert len(strategy._order_updaters.get(market, [])) == (
            7 if event_name == "enable_trading" else 0)

        strategy.apply_live_event({
            "type": event_name,
            "args": {
                "market_type": AvailableMarketTypes.DAY_FORWARD.value,
                "start_time": "2022-06-14T00:00",
                "end_time": "2022-06-15T00:00",
                "capacity_percent": 20.0,
                "energy_rate": 30.0
            }})
        market = area.forward_markets[AvailableMarketTypes.DAY_FORWARD]
        TestForwardLiveEvents._assert_order_count_from_strategy(
            strategy, AvailableMarketTypes.DAY_FORWARD, 24)
        assert len(strategy._order_updaters.get(market, [])) == (
            24 if event_name == "enable_trading" else 0)

        strategy.apply_live_event({
            "type": event_name,
            "args": {
                "market_type": AvailableMarketTypes.WEEK_FORWARD.value,
                "start_time": "2022-06-13T00:00",
                "end_time": "2022-08-01T00:00",
                "capacity_percent": 20.0,
                "energy_rate": 30.0
            }})
        market = area.forward_markets[AvailableMarketTypes.WEEK_FORWARD]
        TestForwardLiveEvents._assert_order_count_from_strategy(
            strategy, AvailableMarketTypes.WEEK_FORWARD, 6)
        assert len(strategy._order_updaters.get(market, [])) == (
            6 if event_name == "enable_trading" else 0)

        strategy.apply_live_event({
            "type": event_name,
            "args": {
                "market_type": AvailableMarketTypes.MONTH_FORWARD.value,
                "start_time": "2022-06-13T00:00",
                "end_time": "2022-12-01T00:00",
                "capacity_percent": 20.0,
                "energy_rate": 30.0
            }})
        market = area.forward_markets[AvailableMarketTypes.MONTH_FORWARD]
        TestForwardLiveEvents._assert_order_count_from_strategy(
            strategy, AvailableMarketTypes.MONTH_FORWARD, 5)
        assert len(strategy._order_updaters.get(market, [])) == (
            5 if event_name == "enable_trading" else 0)

        strategy.apply_live_event({
            "type": event_name,
            "args": {
                "market_type": AvailableMarketTypes.YEAR_FORWARD.value,
                "start_time": "2022-06-13T00:00",
                "end_time": "2025-01-01T00:00",
                "capacity_percent": 20.0,
                "energy_rate": 30.0
            }})
        market = area.forward_markets[AvailableMarketTypes.YEAR_FORWARD]
        TestForwardLiveEvents._assert_order_count_from_strategy(
            strategy, AvailableMarketTypes.YEAR_FORWARD, 2)
        assert len(strategy._order_updaters.get(market, [])) == (
            2 if event_name == "enable_trading" else 0)

    @staticmethod
    @pytest.mark.parametrize("event_name", ["disable_trading", "remove_order"])
    def test_disable_remove_trading_event(forward_strategy_fixture, event_name):
        strategy = forward_strategy_fixture[0]
        area = forward_strategy_fixture[1]
        area.activate()
        strategy.event_market_cycle()
        # First orders need to be created
        strategy.apply_live_event({
            "type": "enable_trading",
            "args": {
                "market_type": AvailableMarketTypes.INTRADAY.value,
                "start_time": "2022-06-13T00:00",
                "end_time": "2022-06-13T02:00",
                "capacity_percent": 20.0,
                "energy_rate": 30.0
            }})
        strategy.apply_live_event({
            "type": event_name,
            "args": {
                "market_type": AvailableMarketTypes.INTRADAY.value,
                "start_time": "2022-06-13T00:00",
                "end_time": "2022-06-13T02:00",
            }})
        market = area.forward_markets[AvailableMarketTypes.INTRADAY]
        TestForwardLiveEvents._assert_order_count_from_strategy(
            strategy, AvailableMarketTypes.INTRADAY, 0)
        assert len(strategy._order_updaters.get(market, [])) == 0
