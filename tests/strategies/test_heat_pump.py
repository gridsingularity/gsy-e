# pylint: disable=protected-access
import os
from math import isclose
from typing import TYPE_CHECKING, Tuple
from unittest.mock import patch, PropertyMock, MagicMock, Mock

import pytest
from gsy_framework.constants_limits import GlobalConfig, ConstSettings, TIME_ZONE
from gsy_framework.data_classes import Trade, TraderDetails
from gsy_framework.enums import AvailableMarketTypes
from pendulum import today, duration

import gsy_e.models.strategy.heat_pump
from gsy_e.gsy_e_core.util import gsye_root_path
from gsy_e.models.area import Area
from gsy_e.models.strategy.heat_pump import HeatPumpStrategy, HeatPumpOrderUpdaterParameters
from gsy_e.models.strategy.virtual_heatpump import VirtualHeatpumpStrategy

if TYPE_CHECKING:
    from gsy_e.models.strategy.trading_strategy_base import TradingStrategyBase

SLOT_LENGTH = duration(hours=1)
CURRENT_MARKET_SLOT = today(tz=TIME_ZONE)
RATE_PROFILE = {CURRENT_MARKET_SLOT: 0, CURRENT_MARKET_SLOT + SLOT_LENGTH: 2}


@pytest.fixture(name="heatpump_fixture")
def fixture_heatpump_strategy(request) -> Tuple["TradingStrategyBase", "Area"]:
    gsy_e.models.strategy.heat_pump.HeatPumpValidator = Mock()
    original_market_type = ConstSettings.MASettings.MARKET_TYPE
    ConstSettings.MASettings.MARKET_TYPE = 2
    strategy_params = request.param if hasattr(request, "param") else {}
    is_virtual_heatpump = strategy_params.pop("is_virtual", False)
    if not is_virtual_heatpump:
        strategy = HeatPumpStrategy(
            consumption_kWh_profile=os.path.join(
                gsye_root_path, "resources", "hp_consumption_kWh.csv"
            ),
            source_temp_C_profile=os.path.join(
                gsye_root_path, "resources", "hp_external_temp_C.csv"
            ),
            **strategy_params
        )
    else:
        strategy = VirtualHeatpumpStrategy(
            water_supply_temp_C_profile=os.path.join(
                gsye_root_path, "resources", "hp_supply_temp_C.csv"
            ),
            water_return_temp_C_profile=os.path.join(
                gsye_root_path, "resources", "hp_return_temp_C.csv"
            ),
            dh_water_flow_m3_profile=os.path.join(
                gsye_root_path, "resources", "hp_water_flow.csv"
            ),
            **strategy_params
        )
    strategy_area = Area("asset", strategy=strategy)
    area = Area("grid", children=[strategy_area])
    area.config.start_date = CURRENT_MARKET_SLOT
    area.config.end_date = area.config.start_date.add(days=1)
    area.activate()
    yield strategy, area
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
    @pytest.mark.parametrize(
        "heatpump_fixture", [{"is_virtual": True}, {"is_virtual": False}], indirect=True
    )
    def test_heatpump_creates_order_updater_on_spot_on_market_cycle(heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        strategy._get_energy_buy_energy = MagicMock(return_value=1)
        strategy.event_market_cycle()
        market_object = area.spot_market
        assert len(strategy._order_updaters[market_object].keys()) == 1

    @pytest.mark.parametrize(
        "heatpump_fixture", [{"is_virtual": True}, {"is_virtual": False}], indirect=True
    )
    def test_heatpump_posts_order_on_spot_on_market_cycle(self, heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        energy_to_buy = 100
        strategy._get_energy_buy_energy = MagicMock(return_value=energy_to_buy)
        strategy.event_market_cycle()
        self._assert_bid(
            list(area.spot_market.bids.values()),
            strategy,
            energy_to_buy,
            GlobalConfig.FEED_IN_TARIFF,
        )

    @pytest.mark.parametrize(
        "heatpump_fixture", [{"is_virtual": True}, {"is_virtual": False}], indirect=True
    )
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
            MagicMock(return_value=True)
        )
        updater_params = strategy._order_updater_params[AvailableMarketTypes.SPOT]
        with patch("gsy_e.models.area.Area.now", new_callable=PropertyMock) as now_mock:
            now_mock.return_value = CURRENT_MARKET_SLOT + updater_params.get_update_interval()
            strategy.event_tick()
            update_interval = duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL
            )
            initial_rate = GlobalConfig.FEED_IN_TARIFF
            final_rate = GlobalConfig.market_maker_rate
            expected_rate = (final_rate - initial_rate) / (
                (duration(minutes=15) - update_interval) / update_interval
            )
            self._assert_bid(
                list(market_object.bids.values()), strategy, energy_to_buy, expected_rate
            )

    @staticmethod
    @pytest.mark.parametrize(
        "heatpump_fixture", [{"is_virtual": True}, {"is_virtual": False}], indirect=True
    )
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
    @pytest.mark.parametrize(
        "heatpump_fixture",
        [
            {"is_virtual": True, "order_updater_parameters": {}},
            {"is_virtual": False, "order_updater_parameters": {}},
        ],
        indirect=True,
    )
    @patch("gsy_framework.constants_limits.GlobalConfig.FEED_IN_TARIFF", 20)
    @patch("gsy_framework.constants_limits.GlobalConfig.market_maker_rate", 30)
    def test_order_updater_parameters_return_default_values_correctly(heatpump_fixture):
        strategy = heatpump_fixture[0]
        strategy._get_energy_buy_energy = MagicMock(return_value=1)
        strategy.event_market_cycle()
        assert (
            strategy._order_updater_params[AvailableMarketTypes.SPOT].get_initial_rate(
                CURRENT_MARKET_SLOT
            )
            == 20
        )
        assert (
            strategy._order_updater_params[AvailableMarketTypes.SPOT].get_final_rate(
                CURRENT_MARKET_SLOT
            )
            == 30
        )

    @staticmethod
    @patch("gsy_framework.constants_limits.GlobalConfig.FEED_IN_TARIFF", RATE_PROFILE)
    @patch("gsy_framework.constants_limits.GlobalConfig.market_maker_rate", RATE_PROFILE)
    @pytest.mark.parametrize(
        "heatpump_fixture",
        [
            {"is_virtual": True, "order_updater_parameters": {}},
            {"is_virtual": False, "order_updater_parameters": {}},
        ],
        indirect=True,
    )
    def test_order_updater_parameters_get_initiated_with_default_profile(heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        strategy._get_energy_buy_energy = MagicMock(return_value=1)
        strategy.event_market_cycle()
        assert (
            strategy._order_updater_params[AvailableMarketTypes.SPOT].get_initial_rate(
                CURRENT_MARKET_SLOT
            )
            == 0
        )
        assert (
            strategy._order_updater_params[AvailableMarketTypes.SPOT].get_final_rate(
                CURRENT_MARKET_SLOT
            )
            == 0
        )
        area.spot_market.time_slot = CURRENT_MARKET_SLOT + SLOT_LENGTH
        area.spot_market.set_open_market_slot_parameters(
            CURRENT_MARKET_SLOT, [area.spot_market.time_slot]
        )
        if isinstance(strategy, VirtualHeatpumpStrategy):
            strategy._energy_params.increase_tanks_temp_update_hp_state = MagicMock()
        strategy.event_market_cycle()
        assert (
            strategy._order_updater_params[AvailableMarketTypes.SPOT].get_initial_rate(
                area.spot_market.time_slot
            )
            == 2
        )
        assert (
            strategy._order_updater_params[AvailableMarketTypes.SPOT].get_initial_rate(
                area.spot_market.time_slot
            )
            == 2
        )

    @staticmethod
    @pytest.mark.parametrize(
        "heatpump_fixture",
        [
            {
                "is_virtual": True,
                "order_updater_parameters": {
                    AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters(
                        initial_rate=0, final_rate=15
                    )
                },
            },
            {
                "is_virtual": False,
                "order_updater_parameters": {
                    AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters(
                        initial_rate=0, final_rate=15
                    )
                },
            },
        ],
        indirect=True,
    )
    def test_order_updater_parameters_get_initiated_with_user_input(heatpump_fixture):
        strategy = heatpump_fixture[0]
        strategy._get_energy_buy_energy = MagicMock(return_value=1)
        strategy.event_market_cycle()
        assert (
            strategy._order_updater_params[AvailableMarketTypes.SPOT].get_initial_rate(
                CURRENT_MARKET_SLOT
            )
            == 0
        )
        assert (
            strategy._order_updater_params[AvailableMarketTypes.SPOT].get_final_rate(
                CURRENT_MARKET_SLOT
            )
            == 15
        )

    @staticmethod
    @pytest.mark.parametrize(
        "heatpump_fixture",
        [
            {
                "is_virtual": True,
                "order_updater_parameters": {
                    AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters(
                        initial_rate={
                            CURRENT_MARKET_SLOT: 1,
                            CURRENT_MARKET_SLOT + SLOT_LENGTH: 2,
                        },
                        final_rate={
                            CURRENT_MARKET_SLOT: 15,
                            CURRENT_MARKET_SLOT + SLOT_LENGTH: 16,
                        },
                    )
                },
            },
            {
                "is_virtual": False,
                "order_updater_parameters": {
                    AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters(
                        initial_rate={
                            CURRENT_MARKET_SLOT: 1,
                            CURRENT_MARKET_SLOT + SLOT_LENGTH: 2,
                        },
                        final_rate={
                            CURRENT_MARKET_SLOT: 15,
                            CURRENT_MARKET_SLOT + SLOT_LENGTH: 16,
                        },
                    )
                },
            },
        ],
        indirect=True,
    )
    def test_order_updater_parameters_get_initiated_with_user_input_profile(heatpump_fixture):
        strategy = heatpump_fixture[0]
        strategy._get_energy_buy_energy = MagicMock(return_value=1)
        strategy.event_market_cycle()
        assert (
            strategy._order_updater_params[AvailableMarketTypes.SPOT].get_initial_rate(
                CURRENT_MARKET_SLOT
            )
            == 1
        )
        assert (
            strategy._order_updater_params[AvailableMarketTypes.SPOT].get_final_rate(
                CURRENT_MARKET_SLOT
            )
            == 15
        )

    @staticmethod
    @pytest.mark.parametrize(
        "heatpump_fixture", [{"is_virtual": True}, {"is_virtual": False}], indirect=True
    )
    def test_get_energy_buy_energy_returns_correct_value(heatpump_fixture):
        strategy = heatpump_fixture[0]
        strategy.preferred_buying_rate = 15
        tank_parameters = strategy._energy_params._state.tanks._tanks_states[0]
        tank_parameters._min_storage_temp_C = 10
        tank_parameters.get_storage_temp_C = MagicMock(return_value=20)
        tank_parameters.get_temp_decrease = MagicMock(return_value=10)
        strategy._energy_params.get_min_energy_demand_kWh = MagicMock(return_value=1)
        strategy._energy_params.get_max_energy_demand_kWh = MagicMock(return_value=2)
        assert strategy._get_energy_buy_energy(14, CURRENT_MARKET_SLOT) == 2
        assert strategy._get_energy_buy_energy(15, CURRENT_MARKET_SLOT) == 2
        assert strategy._get_energy_buy_energy(16, CURRENT_MARKET_SLOT) == 1
        strategy.state.get_storage_temp_C = MagicMock(return_value=20)
        strategy._energy_params._state.heatpump.get_temp_decrease_K = MagicMock(return_value=1)
        assert strategy._get_energy_buy_energy(16, CURRENT_MARKET_SLOT) == 1

    @staticmethod
    @pytest.mark.parametrize(
        "heatpump_fixture", [{"is_virtual": True}, {"is_virtual": False}], indirect=True
    )
    def test_event_bid_traded_calls_ep_event_traded_energy(heatpump_fixture):
        strategy = heatpump_fixture[0]
        area = heatpump_fixture[1]
        traded_energy = 2
        strategy._energy_params.event_traded_energy = Mock()
        trade = Trade(
            "id",
            CURRENT_MARKET_SLOT,
            traded_energy=traded_energy,
            trade_price=1,
            time_slot=CURRENT_MARKET_SLOT,
            buyer=TraderDetails(
                name=strategy.owner.name,
                uuid=strategy.owner.uuid,
                origin=strategy.owner.name,
                origin_uuid=strategy.owner.uuid,
            ),
            seller=TraderDetails("", ""),
        )
        strategy.event_bid_traded(market_id=area.spot_market.id, bid_trade=trade)
        strategy._energy_params.event_traded_energy.assert_called_once_with(
            CURRENT_MARKET_SLOT, traded_energy
        )

    @staticmethod
    def test_deserialize_args_sets_price_settings_to_none_if_not_provided(heatpump_fixture):
        constructor_args = heatpump_fixture[0].deserialize_args({})
        assert constructor_args == {
            "order_updater_parameters": {
                AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters(
                    update_interval=None, initial_rate=None, final_rate=None
                )
            }
        }

        constructor_args = heatpump_fixture[0].deserialize_args(
            {"initial_buying_rate": 2, "update_interval": 5}
        )
        assert constructor_args == {
            "order_updater_parameters": {
                AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters(
                    update_interval=duration(minutes=5), initial_rate=2, final_rate=None
                )
            }
        }

    @staticmethod
    @pytest.mark.parametrize(
        "heatpump_fixture",
        [
            {
                "is_virtual": True,
                "order_updater_parameters": {
                    AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters(
                        initial_rate=0, final_rate=15, use_market_maker_rate=True
                    )
                },
            },
            {
                "is_virtual": False,
                "order_updater_parameters": {
                    AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters(
                        initial_rate=0, final_rate=15, use_market_maker_rate=True
                    )
                },
            },
        ],
        indirect=True,
    )
    def test_order_updater_respects_use_market_maker_rate(heatpump_fixture):
        assert heatpump_fixture[0]._order_updater_params == {
            AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters(
                update_interval=None, initial_rate=0, final_rate=15, use_market_maker_rate=True
            )
        }
        with patch("gsy_e.models.strategy.heat_pump.HeatPumpStrategy.post_order", Mock()):
            heatpump_fixture[0].event_market_cycle()
        assert (
            heatpump_fixture[0]
            ._order_updater_params[AvailableMarketTypes.SPOT]
            .get_final_rate(CURRENT_MARKET_SLOT)
            == 30
        )

    @staticmethod
    def test_deserialize_args_respects_use_market_maker_rate(heatpump_fixture):
        constructor_args = heatpump_fixture[0].deserialize_args(
            {
                "initial_buying_rate": 2,
                "update_interval": 5,
                "final_buying_rate": 25,
                "use_market_maker_rate": True,
            }
        )
        assert constructor_args == {
            "order_updater_parameters": {
                AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters(
                    update_interval=duration(minutes=5),
                    initial_rate=2,
                    final_rate=25,
                    use_market_maker_rate=True,
                )
            }
        }
