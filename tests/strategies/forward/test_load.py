from copy import deepcopy
from typing import TYPE_CHECKING, Tuple
from unittest.mock import patch, PropertyMock

import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.enums import AvailableMarketTypes
from math import isclose
from pendulum import duration, datetime

from gsy_e.models.area import Area
from gsy_e.models.strategy.forward.load import ForwardLoadStrategy
from gsy_e.models.strategy.forward.order_updater import OrderUpdaterParameters

if TYPE_CHECKING:
    from gsy_e.models.strategy.forward import ForwardStrategyBase

CURRENT_MARKET_SLOT = datetime(2022, 6, 13, 0, 0)


@pytest.fixture(name="forward_strategy_fixture")
def load_forward_strategy_fixture() -> Tuple["ForwardStrategyBase", "Area"]:
    """Fixture for the LoadForwardStrategy class."""
    ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = True
    orig_start_date = GlobalConfig.start_date
    strategy = ForwardLoadStrategy(capacity_kW=100, order_updater_parameters={
        AvailableMarketTypes.INTRADAY: OrderUpdaterParameters(duration(minutes=5), 10, 40),
        AvailableMarketTypes.DAY_FORWARD: OrderUpdaterParameters(duration(minutes=30), 20, 40),
        AvailableMarketTypes.WEEK_FORWARD: OrderUpdaterParameters(duration(days=1), 30, 50),
        AvailableMarketTypes.MONTH_FORWARD: OrderUpdaterParameters(duration(weeks=1), 40, 60),
        AvailableMarketTypes.YEAR_FORWARD: OrderUpdaterParameters(duration(months=1), 50, 70)
    })
    strategy_area = Area("load", strategy=strategy)
    area = Area("grid", children=[strategy_area])
    area.config.start_date = CURRENT_MARKET_SLOT
    area.config.end_date = area.config.start_date.add(years=6)
    yield strategy, area
    ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = False
    GlobalConfig.start_date = orig_start_date


class TestForwardLoadStrategy:
    # pylint: disable=protected-access
    @staticmethod
    def _assert_posted_bids_on_markets(strategy, market_type, bid_count, energy_rate, energy):
        intraday = strategy.area.forward_markets[market_type]
        bids = intraday.get_bids().values()
        assert len(bids) == bid_count
        for bid in bids:
            assert bid.energy_rate == energy_rate
            assert bid.energy == energy
            assert bid.buyer == bid.buyer_origin == strategy.owner.name
            assert bid.buyer_id == bid.buyer_origin_id == strategy.owner.uuid

    @staticmethod
    @pytest.mark.parametrize("market_type, expected_order_updater_count, ", [
        (AvailableMarketTypes.INTRADAY, 24 * 4 - 1),
        (AvailableMarketTypes.DAY_FORWARD, 24 * 7 - 1),
        (AvailableMarketTypes.WEEK_FORWARD, 51),
        (AvailableMarketTypes.MONTH_FORWARD, 23),
        (AvailableMarketTypes.YEAR_FORWARD, 5),
    ])
    def test_order_updaters_follow_market_slots(
            forward_strategy_fixture, market_type, expected_order_updater_count):
        strategy = forward_strategy_fixture[0]
        area = forward_strategy_fixture[1]
        area.activate()
        strategy.event_market_cycle()
        market_object = area.forward_markets[market_type]
        assert (
            list(strategy._order_updaters[market_object].keys()) ==
            market_object.market_time_slots)
        assert (
            len(strategy._order_updaters[market_object].keys()) ==
            expected_order_updater_count)

        with patch("gsy_e.models.area.Area.now", new_callable=PropertyMock) as now_mock:
            now_mock.return_value = CURRENT_MARKET_SLOT + duration(months=1)
            strategy.event_market_cycle()
            assert (
                    list(strategy._order_updaters[market_object].keys()) ==
                    market_object.market_time_slots)
            assert (
                    len(strategy._order_updaters[market_object].keys()) ==
                    expected_order_updater_count)

    @classmethod
    def test_load_forward_strategy_posts_bid_on_market_cycle(cls, forward_strategy_fixture):
        strategy = forward_strategy_fixture[0]
        area = forward_strategy_fixture[1]
        area.activate()
        strategy.event_market_cycle()
        cls._assert_posted_bids_on_markets(
            strategy, AvailableMarketTypes.INTRADAY, 24 * 4 - 1, 10, 10)
        cls._assert_posted_bids_on_markets(
            strategy, AvailableMarketTypes.DAY_FORWARD, 24 * 7 - 1, 20, 10)
        cls._assert_posted_bids_on_markets(
            strategy, AvailableMarketTypes.WEEK_FORWARD, 51, 30, 10)
        cls._assert_posted_bids_on_markets(
            strategy, AvailableMarketTypes.MONTH_FORWARD, 23, 40, 10)
        cls._assert_posted_bids_on_markets(strategy, AvailableMarketTypes.YEAR_FORWARD, 5, 50, 10)

    @staticmethod
    @pytest.mark.parametrize("market_type, update_interval, initial_rate, final_rate, ", [
        (AvailableMarketTypes.INTRADAY, duration(minutes=5), 10, 40),
        (AvailableMarketTypes.DAY_FORWARD, duration(minutes=30), 20, 40),
        (AvailableMarketTypes.WEEK_FORWARD, duration(days=1), 30, 50),
        (AvailableMarketTypes.MONTH_FORWARD, duration(weeks=1), 40, 60),
        (AvailableMarketTypes.YEAR_FORWARD, duration(months=1), 50, 70),
    ])
    def test_load_forward_strategy_updates_bids_on_tick(
            forward_strategy_fixture, market_type, update_interval, initial_rate, final_rate):
        strategy = forward_strategy_fixture[0]
        area = forward_strategy_fixture[1]
        area.activate()
        strategy.event_market_cycle()

        old_bids = deepcopy(area.forward_markets[market_type].slot_bid_mapping)
        # Assert that orders are not updated before the update interval
        with patch("gsy_e.models.area.Area.now", new_callable=PropertyMock) as now_mock:
            now_mock.return_value = CURRENT_MARKET_SLOT + update_interval - duration(seconds=1)
            strategy.event_tick()
            updated_bids = area.forward_markets[market_type].slot_bid_mapping
            for time_slot, old_bid_list in old_bids.items():
                if not old_bid_list:
                    continue
                assert updated_bids[time_slot][0].id == old_bid_list[0].id

        # Assert that orders are updated at exactly the update interval
        with patch("gsy_e.models.area.Area.now", new_callable=PropertyMock) as now_mock:
            now_mock.return_value = CURRENT_MARKET_SLOT + update_interval
            strategy.event_tick()
            updated_bids = area.forward_markets[market_type].slot_bid_mapping
            for time_slot, old_bid_list in old_bids.items():
                if not old_bid_list:
                    continue
                updated_bid = updated_bids[time_slot][0]
                assert updated_bid.id != old_bid_list[0].id
                assert updated_bid.energy == old_bid_list[0].energy
                assert updated_bid.buyer_id == old_bid_list[0].buyer_id
                market_params = area.forward_markets[
                    market_type].get_market_parameters_for_market_slot(time_slot)
                slot_completion_ratio = update_interval.total_minutes() / (
                        market_params.close_timestamp - market_params.open_timestamp
                ).total_minutes()
                assert isclose(
                    updated_bid.energy_rate,
                    slot_completion_ratio * (final_rate - initial_rate) + initial_rate
                )
