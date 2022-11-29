# pylint: disable=protected-access
from math import isclose
from typing import TYPE_CHECKING, Tuple
from unittest.mock import patch, PropertyMock, MagicMock

import pytest
from gsy_framework.constants_limits import GlobalConfig, ConstSettings
from gsy_framework.enums import AvailableMarketTypes
from pendulum import datetime

from gsy_e.models.area import Area
from gsy_e.models.strategy.heat_pump import HeatPumpStrategy

if TYPE_CHECKING:
    from gsy_e.models.strategy.new_base_strategy import NewStrategyBase

CURRENT_MARKET_SLOT = datetime(2022, 6, 13, 0, 0)


@pytest.fixture(name="heatpump_fixture")
def heatpump_strategy_fixture() -> Tuple["NewStrategyBase", "Area"]:
    """Heatpump and area fixture."""
    original_market_type = ConstSettings.MASettings.MARKET_TYPE
    ConstSettings.MASettings.MARKET_TYPE = 2
    orig_start_date = GlobalConfig.start_date
    strategy = HeatPumpStrategy()
    strategy_area = Area("asset", strategy=strategy)
    area = Area("grid", children=[strategy_area])
    area.config.start_date = CURRENT_MARKET_SLOT
    area.config.end_date = area.config.start_date.add(days=1)
    yield strategy, area
    GlobalConfig.start_date = orig_start_date
    ConstSettings.MASettings.MARKET_TYPE = original_market_type


class TestHeatPumpStrategy:

    @staticmethod
    def _assert_bid(orders, strategy, energy_to_buy, energy_rate):
        assert len(orders) == 1
        order = orders[0]
        assert isclose(order.energy_rate, energy_rate, abs_tol=1e-5)
        assert order.energy == energy_to_buy
        assert order.buyer == order.buyer_origin == strategy.owner.name
        assert order.buyer_id == order.buyer_origin_id == strategy.owner.uuid

    @staticmethod
    def test_heatpump_creates_order_updater_on_spot_on_market_cycle(heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        area.activate()
        strategy.event_market_cycle()
        market_object = area.spot_market
        assert len(strategy._order_updaters[market_object].keys()) == 1

    @staticmethod
    @patch("gsy_framework.constants_limits.ConstSettings.FutureMarketSettings."
           "FUTURE_MARKET_DURATION_HOURS", 1)
    def test_heatpump_creates_order_updater_on_futures_on_market_cycle(heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        area.activate()
        strategy.event_market_cycle()
        market_object = area.future_markets
        assert len(strategy._order_updaters[market_object].keys()) == 4

    def test_heatpump_posts_order_on_spot_on_market_cycle(self, heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        area.activate()
        energy_to_buy = 100
        strategy._get_energy_buy_energy = MagicMock(return_value=energy_to_buy)
        strategy.event_market_cycle()
        self._assert_bid(list(area.spot_market.bids.values()), strategy, energy_to_buy, 0)

    @patch("gsy_framework.constants_limits.ConstSettings.FutureMarketSettings."
           "FUTURE_MARKET_DURATION_HOURS", 1)
    def test_heatpump_posts_order_on_futures_on_market_cycle(self, heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        area.activate()
        energy_to_buy = 100
        strategy._get_energy_buy_energy = MagicMock(return_value=energy_to_buy)
        strategy.event_market_cycle()
        assert len(area.future_markets.market_time_slots) == 4
        market_object = area.future_markets
        expected_rates = [37.5, 25, 12.5, 0]
        for ii, market_slot in enumerate(market_object.market_time_slots):
            self._assert_bid(market_object.bids.slot_order_mapping[market_slot],
                             strategy, energy_to_buy, expected_rates[ii])

    def test_orders_are_updated_correctly_on_spot_on_tick(self, heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        area.activate()
        energy_to_buy = 100
        strategy._get_energy_buy_energy = MagicMock(return_value=energy_to_buy)
        # post initial bid
        strategy.event_market_cycle()
        market_object = area.spot_market
        strategy._order_updaters[market_object][market_object.time_slot].is_time_for_update = (
            MagicMock(return_value=True))
        updater_params = strategy._order_updater_params[AvailableMarketTypes.SPOT]
        with patch("gsy_e.models.area.Area.now", new_callable=PropertyMock) as now_mock:
            now_mock.return_value = (
                    CURRENT_MARKET_SLOT + updater_params.update_interval)
            strategy.event_tick()
            # 15 minutes / 30 cts --> 2 ct/kWh after 1minute
            self._assert_bid(list(market_object.bids.values()), strategy, energy_to_buy, 2)

    @patch("gsy_framework.constants_limits.ConstSettings.FutureMarketSettings."
           "FUTURE_MARKET_DURATION_HOURS", 1)
    def test_orders_are_updated_correctly_on_future_on_tick(self, heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        area.activate()
        energy_to_buy = 100
        strategy._get_energy_buy_energy = MagicMock(return_value=energy_to_buy)
        # post initial bid
        strategy.event_market_cycle()
        market_object = area.future_markets
        for market_slot in market_object.market_time_slots:
            strategy._order_updaters[market_object][market_slot].is_time_for_update = (
                MagicMock(return_value=True))
        updater_params = strategy._order_updater_params[AvailableMarketTypes.FUTURE]
        with patch("gsy_e.models.area.Area.now", new_callable=PropertyMock) as now_mock:
            now_mock.return_value = (
                    CURRENT_MARKET_SLOT + updater_params.update_interval)
            strategy.event_tick()

            expected_rates = [37.5, 25, 12.5, 0]
            for ii, market_slot in enumerate(market_object.market_time_slots):
                # future bids should be increased by 12.5/3 after the first update_interval:
                # (50cts / 4 market slots / 3 updates_per_market_slot)
                self._assert_bid(market_object.bids.slot_order_mapping[market_slot],
                                 strategy, energy_to_buy, expected_rates[ii] + 12.5/3)

    @staticmethod
    def test_remove_open_orders_removes_all_orders_on_spot(heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        area.activate()
        energy_to_buy = 100
        strategy._get_energy_buy_energy = MagicMock(return_value=energy_to_buy)
        # post initial bid
        strategy.event_market_cycle()
        market_object = area.spot_market
        strategy.remove_open_orders(market_object, market_object.time_slot)
        orders = list(market_object.bids.values())
        assert len(orders) == 0

    @staticmethod
    def test_remove_open_orders_removes_all_orders_on_futures(heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        area.activate()
        energy_to_buy = 100
        strategy._get_energy_buy_energy = MagicMock(return_value=energy_to_buy)
        # post initial bid
        strategy.event_market_cycle()
        market_object = area.future_markets
        for market_slot in market_object.market_time_slots:
            strategy.remove_open_orders(market_object, market_object.time_slot)
            assert len(market_object.bids.slot_order_mapping[market_slot]) == 0
