# pylint: disable=protected-access
from math import isclose
from typing import TYPE_CHECKING, Tuple
from unittest.mock import patch, PropertyMock, MagicMock

import pytest
from gsy_framework.constants_limits import GlobalConfig, ConstSettings
from gsy_framework.enums import AvailableMarketTypes
from pendulum import datetime

from gsy_e.models.area import Area
from gsy_e.models.strategy.heat_pump import HeatPumpStrategy, HeatPumpOrderUpdaterParameters

if TYPE_CHECKING:
    from gsy_e.models.strategy.trading_strategy_base import TradingStrategyBase

CURRENT_MARKET_SLOT = datetime(2022, 6, 13, 0, 0)
RATE_PROFILE = {CURRENT_MARKET_SLOT: 0, CURRENT_MARKET_SLOT.add(minutes=15): 2}


@pytest.fixture(name="heatpump_fixture")
def fixture_heatpump_strategy(request) -> Tuple["TradingStrategyBase", "Area"]:
    original_market_type = ConstSettings.MASettings.MARKET_TYPE
    ConstSettings.MASettings.MARKET_TYPE = 2
    orig_start_date = GlobalConfig.start_date
    strategy_params = request.param if hasattr(request, "param") else {}
    strategy = HeatPumpStrategy(**strategy_params)
    strategy_area = Area("asset", strategy=strategy)
    area = Area("grid", children=[strategy_area])
    area.config.start_date = CURRENT_MARKET_SLOT
    area.config.end_date = area.config.start_date.add(days=1)
    area.activate()
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
        assert order.buyer.name == order.buyer.origin == strategy.owner.name
        assert order.buyer.uuid == order.buyer.origin_uuid == strategy.owner.uuid

    @staticmethod
    def test_heatpump_creates_order_updater_on_spot_on_market_cycle(heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        strategy.event_market_cycle()
        market_object = area.spot_market
        assert len(strategy._order_updaters[market_object].keys()) == 1

    def test_heatpump_posts_order_on_spot_on_market_cycle(self, heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        energy_to_buy = 100
        strategy._get_energy_buy_energy = MagicMock(return_value=energy_to_buy)
        strategy.event_market_cycle()
        self._assert_bid(list(area.spot_market.bids.values()), strategy, energy_to_buy,
                         GlobalConfig.FEED_IN_TARIFF)

    @patch("gsy_framework.constants_limits.GlobalConfig.FEED_IN_TARIFF", 0)
    @patch("gsy_framework.constants_limits.GlobalConfig.market_maker_rate", 15)
    def test_orders_are_updated_correctly_on_spot_on_tick(self, heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
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
            # 15 minutes / 15 cts --> 1 ct/kWh after 1 minute
            self._assert_bid(list(market_object.bids.values()), strategy, energy_to_buy, 1)

    @staticmethod
    def test_remove_open_orders_removes_all_orders_on_spot(heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        energy_to_buy = 100
        strategy._get_energy_buy_energy = MagicMock(return_value=energy_to_buy)
        # post initial bid
        strategy.event_market_cycle()
        market_object = area.spot_market
        strategy.remove_open_orders(market_object, market_object.time_slot)
        orders = list(market_object.bids.values())
        assert len(orders) == 0

    @staticmethod
    @pytest.mark.parametrize("heatpump_fixture", [{"order_updater_parameters": {}}], indirect=True)
    def test_order_updater_parameters_get_initiated_with_default_values(heatpump_fixture):
        strategy = heatpump_fixture[0]
        strategy.event_market_cycle()
        assert strategy._order_updater_params[AvailableMarketTypes.SPOT].initial_rate == (
            GlobalConfig.FEED_IN_TARIFF)
        assert strategy._order_updater_params[
                   AvailableMarketTypes.SPOT].final_rate == GlobalConfig.market_maker_rate

    @staticmethod
    @patch("gsy_framework.constants_limits.GlobalConfig.FEED_IN_TARIFF", RATE_PROFILE)
    @patch("gsy_framework.constants_limits.GlobalConfig.market_maker_rate", RATE_PROFILE)
    @pytest.mark.parametrize("heatpump_fixture", [{"order_updater_parameters": {}}], indirect=True)
    def test_order_updater_parameters_get_initiated_with_default_profile(heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        strategy.event_market_cycle()
        assert strategy._order_updater_params[AvailableMarketTypes.SPOT].initial_rate == 0
        assert strategy._order_updater_params[
                   AvailableMarketTypes.SPOT].final_rate == 0
        area.spot_market.time_slot = CURRENT_MARKET_SLOT.add(minutes=15)
        area.spot_market.set_open_market_slot_parameters(CURRENT_MARKET_SLOT,
                                                         [area.spot_market.time_slot])
        strategy.event_market_cycle()
        assert strategy._order_updater_params[AvailableMarketTypes.SPOT].initial_rate == 2
        assert strategy._order_updater_params[
                   AvailableMarketTypes.SPOT].final_rate == 2

    @staticmethod
    @pytest.mark.parametrize("heatpump_fixture", [
        {"order_updater_parameters": {
            AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters(initial_rate=0,
                                                                      final_rate=15)}}
    ], indirect=True)
    def test_order_updater_parameters_get_initiated_with_user_input(heatpump_fixture):
        strategy = heatpump_fixture[0]
        strategy.event_market_cycle()
        assert strategy._order_updater_params[AvailableMarketTypes.SPOT].initial_rate == 0
        assert strategy._order_updater_params[AvailableMarketTypes.SPOT].final_rate == 15
