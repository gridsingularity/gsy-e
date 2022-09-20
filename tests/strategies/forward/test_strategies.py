from copy import deepcopy
from math import isclose
from typing import TYPE_CHECKING, Tuple
from unittest.mock import patch, PropertyMock

import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.enums import AvailableMarketTypes
from pendulum import duration, datetime

from gsy_e.models.area import Area
from gsy_e.models.strategy.forward.load import ForwardLoadStrategy
from gsy_e.models.strategy.forward.order_updater import OrderUpdaterParameters
from gsy_e.models.strategy.forward.pv import ForwardPVStrategy

if TYPE_CHECKING:
    from gsy_e.models.strategy.forward import ForwardStrategyBase

CURRENT_MARKET_SLOT = datetime(2022, 6, 13, 0, 0)

load_parameters = {
    AvailableMarketTypes.INTRADAY: OrderUpdaterParameters(duration(minutes=5), 10, 40, 20),
    AvailableMarketTypes.DAY_FORWARD: OrderUpdaterParameters(duration(minutes=30), 20, 40, 20),
    AvailableMarketTypes.WEEK_FORWARD: OrderUpdaterParameters(duration(days=1), 30, 50, 20),
    AvailableMarketTypes.MONTH_FORWARD: OrderUpdaterParameters(duration(weeks=1), 40, 60, 20),
    AvailableMarketTypes.YEAR_FORWARD: OrderUpdaterParameters(duration(months=1), 50, 70, 20)
}


pv_parameters = {
    AvailableMarketTypes.INTRADAY: OrderUpdaterParameters(duration(minutes=5), 41, 11, 20),
    AvailableMarketTypes.DAY_FORWARD: OrderUpdaterParameters(duration(minutes=30), 42, 22, 20),
    AvailableMarketTypes.WEEK_FORWARD: OrderUpdaterParameters(duration(days=1), 53, 33, 20),
    AvailableMarketTypes.MONTH_FORWARD: OrderUpdaterParameters(duration(weeks=1), 66, 39, 20),
    AvailableMarketTypes.YEAR_FORWARD: OrderUpdaterParameters(duration(months=1), 72, 56, 20)
}


@pytest.fixture(name="forward_strategy_fixture", params=[
    (ForwardLoadStrategy, load_parameters,),
    (ForwardPVStrategy, pv_parameters, )])
def forward_market_strategy_fixture(request) -> Tuple["ForwardStrategyBase", "Area"]:
    """Fixture for the ForwardStrategy classes."""
    ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = True
    orig_start_date = GlobalConfig.start_date
    strategy = request.param[0](capacity_kW=100, order_updater_parameters=request.param[1])
    strategy_area = Area("asset", strategy=strategy)
    area = Area("grid", children=[strategy_area])
    area.config.start_date = CURRENT_MARKET_SLOT
    area.config.end_date = area.config.start_date.add(years=20)
    yield strategy, area
    ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = False
    GlobalConfig.start_date = orig_start_date


class TestForwardStrategies:
    # pylint: disable=protected-access
    @staticmethod
    def _assert_posted_orders_on_markets(strategy, market_type, order_count, energy_rate, energy):
        intraday = strategy.area.forward_markets[market_type]
        if isinstance(strategy, ForwardLoadStrategy):
            orders = intraday.get_bids().values()
        else:
            orders = intraday.get_offers().values()

        assert len(orders) == order_count
        for order in orders:
            assert order.energy_rate == energy_rate
            assert order.energy == energy
            assert order.buyer == order.buyer_origin == strategy.owner.name
            assert order.buyer_id == order.buyer_origin_id == strategy.owner.uuid

    @staticmethod
    @pytest.mark.parametrize("market_type, expected_order_updater_count, next_slot_timestamp, ", [
        (AvailableMarketTypes.INTRADAY, 24 * 4 - 1,
         CURRENT_MARKET_SLOT.add(minutes=15)),
        (AvailableMarketTypes.DAY_FORWARD, 24 * 7 - 1,
         CURRENT_MARKET_SLOT.add(days=1)),
        (AvailableMarketTypes.WEEK_FORWARD, 51,
         CURRENT_MARKET_SLOT.start_of("week").add(weeks=1)),
        (AvailableMarketTypes.MONTH_FORWARD, 23,
         CURRENT_MARKET_SLOT.start_of("month").add(months=1)),
        (AvailableMarketTypes.YEAR_FORWARD, 5,
         CURRENT_MARKET_SLOT.start_of("year").add(years=1)),
    ])
    def test_order_updaters_follow_market_slots(
            forward_strategy_fixture, market_type,
            expected_order_updater_count, next_slot_timestamp):
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
            now_mock.return_value = next_slot_timestamp
            area.cycle_markets()
            # strategy.event_market_cycle()
            assert (
                    len(strategy._order_updaters[market_object].keys()) ==
                    expected_order_updater_count)
            assert (
                    list(strategy._order_updaters[market_object].keys()) ==
                    market_object.market_time_slots)

    @classmethod
    def test_forward_strategy_posts_order_on_market_cycle(cls, forward_strategy_fixture):
        strategy = forward_strategy_fixture[0]
        area = forward_strategy_fixture[1]
        area.activate()
        strategy.event_market_cycle()
        cls._assert_posted_orders_on_markets(
            strategy, AvailableMarketTypes.INTRADAY, 24 * 4 - 1, 10, 10)
        cls._assert_posted_orders_on_markets(
            strategy, AvailableMarketTypes.DAY_FORWARD, 24 * 7 - 1, 20, 10)
        cls._assert_posted_orders_on_markets(
            strategy, AvailableMarketTypes.WEEK_FORWARD, 51, 30, 10)
        cls._assert_posted_orders_on_markets(
            strategy, AvailableMarketTypes.MONTH_FORWARD, 23, 40, 10)
        cls._assert_posted_orders_on_markets(strategy, AvailableMarketTypes.YEAR_FORWARD,
                                             5, 50, 10)

    @staticmethod
    @pytest.mark.parametrize("market_type, ", [
        AvailableMarketTypes.INTRADAY,
        AvailableMarketTypes.DAY_FORWARD,
        AvailableMarketTypes.WEEK_FORWARD,
        AvailableMarketTypes.MONTH_FORWARD,
        AvailableMarketTypes.YEAR_FORWARD,
    ])
    def test_forward_strategy_updates_orders_on_tick(
            forward_strategy_fixture, market_type):
        strategy = forward_strategy_fixture[0]
        area = forward_strategy_fixture[1]
        area.activate()
        strategy.event_market_cycle()

        update_interval = strategy._order_updater_params[market_type].update_interval
        initial_rate = strategy._order_updater_params[market_type].initial_rate
        final_rate = strategy._order_updater_params[market_type].final_rate

        if isinstance(strategy, ForwardPVStrategy):
            order_mapping = area.forward_markets[market_type].slot_offer_mapping
        else:
            order_mapping = area.forward_markets[market_type].slot_bid_mapping
        old_orders = deepcopy(order_mapping)
        # Assert that orders are not updated before the update interval
        with patch("gsy_e.models.area.Area.now", new_callable=PropertyMock) as now_mock:
            now_mock.return_value = CURRENT_MARKET_SLOT + update_interval - duration(seconds=1)
            strategy.event_tick()
            assert len(order_mapping) > 0
            for time_slot, old_order_list in old_orders.items():
                if not old_order_list:
                    continue
                assert order_mapping[time_slot][0].id == old_order_list[0].id

        # Assert that orders are updated at exactly the update interval
        with patch("gsy_e.models.area.Area.now", new_callable=PropertyMock) as now_mock:
            now_mock.return_value = CURRENT_MARKET_SLOT + update_interval
            strategy.event_tick()
            assert len(order_mapping) > 0
            for time_slot, old_order_list in old_orders.items():
                if not old_order_list:
                    continue
                updated_order = order_mapping[time_slot][0]
                assert updated_order.id != old_order_list[0].id
                assert updated_order.energy == old_order_list[0].energy
                if isinstance(strategy, ForwardPVStrategy):
                    assert updated_order.seller_id == old_order_list[0].seller_id
                else:
                    assert updated_order.buyer_id == old_order_list[0].buyer_id
                market_params = area.forward_markets[
                    market_type].get_market_parameters_for_market_slot(time_slot)
                slot_completion_ratio = update_interval.total_minutes() / (
                        market_params.close_timestamp - market_params.open_timestamp
                ).total_minutes()
                if isinstance(strategy, ForwardPVStrategy):
                    assert isclose(
                        updated_order.energy_rate,
                        initial_rate - slot_completion_ratio * abs(initial_rate - final_rate))
                else:
                    assert isclose(
                        updated_order.energy_rate,
                        slot_completion_ratio * (final_rate - initial_rate) + initial_rate)
