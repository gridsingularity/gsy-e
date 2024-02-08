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
# pylint: disable=protected-access, no-self-use
import json
import uuid
from collections import deque
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.data_classes import Bid, Offer, Trade, TraderDetails
from gsy_framework.utils import format_datetime
from parameterized import parameterized
from pendulum import datetime, duration, now
from redis.exceptions import RedisError

import gsy_e.constants
import gsy_e.gsy_e_core.util
from gsy_e.gsy_e_core.global_objects_singleton import global_objects
from gsy_e.models.area import Area, CoefficientArea
from gsy_e.models.strategy import BidEnabledStrategy
from gsy_e.models.strategy.external_strategies import (
    IncomingRequest, ExternalStrategyConnectionManager)
from gsy_e.models.strategy.external_strategies.load import (
    LoadHoursForecastExternalStrategy, LoadProfileForecastExternalStrategy,
    LoadHoursExternalStrategy, LoadProfileExternalStrategy)
from gsy_e.models.strategy.external_strategies.pv import (
    PVExternalStrategy, PVForecastExternalStrategy, PVPredefinedExternalStrategy,
    PVUserProfileExternalStrategy)
from gsy_e.models.strategy.external_strategies.storage import StorageExternalStrategy
from gsy_e.models.strategy.scm import SCMStrategy

transaction_id = str(uuid.uuid4())


@pytest.fixture(name="ext_strategy_fixture")
def fixture_ext_strategy(request):
    strategy = request.param
    config = Mock()
    config.slot_length = duration(minutes=15)
    config.tick_length = duration(seconds=15)
    config.ticks_per_slot = 60
    config.start_date = GlobalConfig.start_date
    config.grid_fee_type = ConstSettings.MASettings.GRID_FEE_TYPE
    config.end_date = GlobalConfig.start_date + duration(days=1)
    if isinstance(strategy, SCMStrategy):
        area = CoefficientArea(
            name="forecast_pv", config=config, strategy=strategy, grid_fee_constant=0.0)
        parent = CoefficientArea(
            name="parent_area", children=[area], config=config, grid_fee_constant=0.0)
        parent.activate_energy_parameters(GlobalConfig.start_date)
        area.activate_energy_parameters(GlobalConfig.start_date)
    else:
        area = Area(name="forecast_pv", config=config, strategy=strategy,
                    external_connection_available=True)
        parent = Area(name="parent_area", children=[area], config=config)
        parent.activate()
    strategy.connected = True
    market = MagicMock()
    market.time_slot = GlobalConfig.start_date
    return strategy


class TestExternalMixin:

    def _create_and_activate_strategy_area(self, strategy):
        self.config = MagicMock()
        self.config.capacity_kW = 0.160
        self.config.ticks_per_slot = 90
        GlobalConfig.end_date = GlobalConfig.start_date + duration(days=1)
        self.area = Area(name="test_area", config=self.config, strategy=strategy,
                         external_connection_available=True)
        self.parent = Area(name="parent_area", children=[self.area])
        self.parent.activate()
        global_objects.external_global_stats(self.area, self.config.ticks_per_slot)
        strategy.connected = True
        market = MagicMock()
        market.time_slot = GlobalConfig.start_date
        self.parent.get_future_market_from_id = lambda _: market
        self.area.get_future_market_from_id = lambda _: market

    @staticmethod
    def teardown_method() -> None:
        ConstSettings.MASettings.MARKET_TYPE = 1

    def test_dispatch_tick_frequency_gets_calculated_correctly(self):
        self.external_strategy = LoadHoursExternalStrategy(100)
        self._create_and_activate_strategy_area(self.external_strategy)
        gsy_e.gsy_e_core.util.gsy_e.constants.DISPATCH_EVENT_TICK_FREQUENCY_PERCENT = 20
        self.config.ticks_per_slot = 90
        global_objects.external_global_stats(self.area, self.config.ticks_per_slot)
        assert global_objects.external_global_stats.\
            external_tick_counter._dispatch_tick_frequency == 18
        self.config.ticks_per_slot = 10
        global_objects.external_global_stats(self.area, self.config.ticks_per_slot)
        assert global_objects.external_global_stats.\
            external_tick_counter._dispatch_tick_frequency == 2
        self.config.ticks_per_slot = 100
        global_objects.external_global_stats(self.area, self.config.ticks_per_slot)
        assert global_objects.external_global_stats.\
            external_tick_counter._dispatch_tick_frequency == 20
        self.config.ticks_per_slot = 99
        global_objects.external_global_stats(self.area, self.config.ticks_per_slot)
        assert global_objects.external_global_stats.\
            external_tick_counter._dispatch_tick_frequency == 19
        gsy_e.gsy_e_core.util.gsy_e.constants.DISPATCH_EVENT_TICK_FREQUENCY_PERCENT = 50
        self.config.ticks_per_slot = 90
        global_objects.external_global_stats(self.area, self.config.ticks_per_slot)
        assert global_objects.external_global_stats.\
            external_tick_counter._dispatch_tick_frequency == 45
        self.config.ticks_per_slot = 10
        global_objects.external_global_stats(self.area, self.config.ticks_per_slot)
        assert global_objects.external_global_stats.\
            external_tick_counter._dispatch_tick_frequency == 5
        self.config.ticks_per_slot = 100
        global_objects.external_global_stats(self.area, self.config.ticks_per_slot)
        assert global_objects.external_global_stats.\
            external_tick_counter._dispatch_tick_frequency == 50
        self.config.ticks_per_slot = 99
        global_objects.external_global_stats(self.area, self.config.ticks_per_slot)
        assert global_objects.external_global_stats.\
            external_tick_counter._dispatch_tick_frequency == 49

    @parameterized.expand([
        [LoadHoursExternalStrategy(100)],
        [PVExternalStrategy(2, capacity_kW=0.16)],
        [StorageExternalStrategy()]
    ])
    def test_dispatch_event_tick_to_external_aggregator(self, strategy):
        gsy_e.gsy_e_core.util.gsy_e.constants.DISPATCH_EVENT_TICK_FREQUENCY_PERCENT = 20
        self._create_and_activate_strategy_area(strategy)
        strategy.redis.aggregator.is_controlling_device = lambda _: True
        self.config.ticks_per_slot = 90
        strategy.event_activate()
        assert global_objects.external_global_stats.\
            external_tick_counter._dispatch_tick_frequency == 18
        self.area.current_tick = 1
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.aggregator.add_batch_tick_event.assert_not_called()
        self.area.current_tick = 17
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.aggregator.add_batch_tick_event.assert_not_called()
        self.area.current_tick = 18
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.aggregator.add_batch_tick_event.assert_called_once()
        assert strategy.redis.aggregator.add_batch_tick_event.call_args_list[0][0][0] == \
            self.area.uuid
        result = strategy.redis.aggregator.add_batch_tick_event.call_args_list[0][0][1]
        assert result == \
            {"market_slot": GlobalConfig.start_date.format(gsy_e.constants.DATE_TIME_FORMAT),
             "slot_completion": "20%"}
        strategy.redis.reset_mock()
        strategy.redis.aggregator.add_batch_tick_event.reset_mock()
        self.area.current_tick = 35
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.aggregator.add_batch_tick_event.assert_not_called()
        self.area.current_tick = 36
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.aggregator.add_batch_tick_event.assert_called_once()
        assert strategy.redis.aggregator.add_batch_tick_event.call_args_list[0][0][0] == \
            self.area.uuid
        result = strategy.redis.aggregator.add_batch_tick_event.call_args_list[0][0][1]
        assert result == \
            {"market_slot": GlobalConfig.start_date.format(gsy_e.constants.DATE_TIME_FORMAT),
             "slot_completion": "40%"}

    @parameterized.expand([
        [LoadHoursExternalStrategy(100)],
        [PVExternalStrategy(2, capacity_kW=0.16)],
        [StorageExternalStrategy()]
    ])
    def test_dispatch_event_tick_to_external_agent(self, strategy):
        gsy_e.gsy_e_core.util.gsy_e.constants.DISPATCH_EVENT_TICK_FREQUENCY_PERCENT = 20
        self._create_and_activate_strategy_area(strategy)
        strategy.redis.aggregator.is_controlling_device = lambda _: False
        self.config.ticks_per_slot = 90
        strategy.event_activate()
        assert global_objects.external_global_stats.\
            external_tick_counter._dispatch_tick_frequency == 18
        self.area.current_tick = 1
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.publish_json.assert_not_called()
        self.area.current_tick = 17
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.publish_json.assert_not_called()
        self.area.current_tick = 18
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.publish_json.assert_called_once()
        assert strategy.redis.publish_json.call_args_list[0][0][0] == "test_area/events/tick"
        result = strategy.redis.publish_json.call_args_list[0][0][1]
        result.pop("area_uuid")
        assert result == \
            {"slot_completion": "20%",
             "market_slot": GlobalConfig.start_date.format(gsy_e.constants.DATE_TIME_FORMAT),
             "event": "tick",
             "device_info": strategy._device_info_dict}

        strategy.redis.reset_mock()
        strategy.redis.publish_json.reset_mock()
        self.area.current_tick = 35
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.publish_json.assert_not_called()
        self.area.current_tick = 36
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.publish_json.assert_called_once()
        assert strategy.redis.publish_json.call_args_list[0][0][0] == "test_area/events/tick"
        result = strategy.redis.publish_json.call_args_list[0][0][1]
        result.pop("area_uuid")
        assert result == \
            {"slot_completion": "40%",
             "market_slot": GlobalConfig.start_date.format(gsy_e.constants.DATE_TIME_FORMAT),
             "event": "tick",
             "device_info": strategy._device_info_dict}

    @parameterized.expand([
        [LoadHoursExternalStrategy(100),
         Bid("bid_id", now(), 20, 1.0, TraderDetails("test_area", ""))],
        [PVExternalStrategy(2, capacity_kW=0.16),
         Offer("offer_id", now(), 20, 1.0, TraderDetails("test_area", ""))],
        [StorageExternalStrategy(),
         Bid("bid_id", now(), 20, 1.0, TraderDetails("test_area", ""))],
        [StorageExternalStrategy(),
         Offer("offer_id", now(), 20, 1.0, TraderDetails("test_area", ""))]
    ])
    def test_dispatch_event_trade_to_external_aggregator(self, strategy, offer_bid):
        strategy._track_energy_sell_type = lambda _: None
        self._create_and_activate_strategy_area(strategy)
        strategy.redis.aggregator.is_controlling_device = lambda _: True
        market = self.area.get_future_market_from_id(1)
        self.area._markets.markets = {1: market}
        strategy.state._available_energy_kWh = {market.time_slot: 1000.0}
        strategy.state.pledged_sell_kWh = {market.time_slot: 0.0}
        strategy.state.offered_sell_kWh = {market.time_slot: 0.0}
        current_time = now()
        if isinstance(offer_bid, Bid):
            self.area.strategy.add_bid_to_posted(market.id, offer_bid)
            trade = Trade("id", current_time,
                          TraderDetails("parent_area", str(self.area.uuid)),
                          TraderDetails("test_area", str(self.parent.uuid)),
                          fee_price=0.23, bid=offer_bid,
                          traded_energy=1, trade_price=20)
        else:
            self.area.strategy.offers.post(offer_bid, market.id)
            trade = Trade("id", current_time,
                          TraderDetails("test_area", str(self.parent.uuid)),
                          TraderDetails("parent_area", str(self.area.uuid)),
                          fee_price=0.23, offer=offer_bid,
                          traded_energy=1, trade_price=20)

        strategy.event_offer_traded(market_id="test_market", trade=trade)
        assert strategy.redis.aggregator.add_batch_trade_event.call_args_list[0][0][0] == \
            self.area.uuid

        call_args = strategy.redis.aggregator.add_batch_trade_event.call_args_list[0][0][1]
        assert set(call_args.keys()) == {"residual_bid_id", "asset_id", "buyer",
                                         "local_market_fee", "residual_offer_id", "total_fee",
                                         "traded_energy", "bid_id", "time", "seller",
                                         "trade_price", "trade_id", "offer_id", "event",
                                         "seller_origin", "buyer_origin"}
        assert call_args["trade_id"] == trade.id
        assert call_args["asset_id"] == self.area.uuid
        assert call_args["event"] == "trade"
        assert call_args["trade_price"] == 20
        assert call_args["traded_energy"] == 1.0
        assert call_args["total_fee"] == 0.23
        assert call_args["time"] == current_time.isoformat()
        assert call_args["residual_bid_id"] == "None"
        assert call_args["residual_offer_id"] == "None"
        if isinstance(offer_bid, Bid):
            assert call_args["bid_id"] == trade.match_details["bid"].id
            assert call_args["offer_id"] == "None"
            assert call_args["seller"] == trade.seller.name
            assert call_args["buyer"] == "anonymous"
        else:
            assert call_args["bid_id"] == "None"
            assert call_args["offer_id"] == trade.match_details["offer"].id
            assert call_args["seller"] == "anonymous"
            assert call_args["buyer"] == trade.buyer.name

    @parameterized.expand([
        [LoadHoursExternalStrategy(100)],
        [PVExternalStrategy(2, capacity_kW=0.16)],
        [StorageExternalStrategy()]
    ])
    def test_dispatch_event_trade_to_external_agent(self, strategy):
        strategy._track_energy_sell_type = lambda _: None
        self._create_and_activate_strategy_area(strategy)
        strategy.redis.aggregator.is_controlling_device = lambda _: False
        market = self.area.get_future_market_from_id(1)
        self.area._markets.markets = {1: market}
        strategy.state._available_energy_kWh = {market.time_slot: 1000.0}
        strategy.state.pledged_sell_kWh = {market.time_slot: 0.0}
        strategy.state.offered_sell_kWh = {market.time_slot: 0.0}
        current_time = now()
        trade = Trade("id", current_time,
                      TraderDetails("test_area", str(self.area.uuid)),
                      TraderDetails("parent_area", str(self.parent.uuid)),
                      fee_price=0.23,
                      offer=Offer("offer_id", now(), 20, 1.0,
                                  TraderDetails("test_area", str(self.area.uuid))),
                      traded_energy=1, trade_price=20)
        strategy.event_offer_traded(market_id="test_market", trade=trade)
        assert strategy.redis.publish_json.call_args_list[0][0][0] == "test_area/events/trade"
        call_args = strategy.redis.publish_json.call_args_list[0][0][1]
        assert call_args["trade_id"] == trade.id
        assert call_args["event"] == "trade"
        assert call_args["trade_price"] == 20
        assert call_args["traded_energy"] == 1.0
        assert call_args["fee_price"] == 0.23
        assert call_args["offer_id"] == trade.match_details["offer"].id
        assert call_args["residual_id"] == "None"
        assert call_args["time"] == current_time.isoformat()
        assert call_args["seller"] == trade.seller.name
        assert call_args["buyer"] == "anonymous"
        assert call_args["device_info"] == strategy._device_info_dict

    @parameterized.expand([
        [LoadHoursExternalStrategy(100)],
        [PVExternalStrategy(2, capacity_kW=0.16)],
        [StorageExternalStrategy()]
    ])
    def test_skip_dispatch_double_event_trade_to_external_agent_two_sided_market(self, strategy):
        ConstSettings.MASettings.MARKET_TYPE = 2
        strategy._track_energy_sell_type = lambda _: None
        self._create_and_activate_strategy_area(strategy)
        market = self.area.get_future_market_from_id(1)
        self.area._markets.markets = {1: market}
        strategy.state._available_energy_kWh = {market.time_slot: 1000.0}
        strategy.state.pledged_sell_kWh = {market.time_slot: 0.0}
        strategy.state.offered_sell_kWh = {market.time_slot: 0.0}
        current_time = now()
        if isinstance(strategy, BidEnabledStrategy):
            bid = Bid("offer_id", now(), 20, 1.0, TraderDetails("test_area", strategy.owner.uuid))
            strategy.add_bid_to_posted(market.id, bid)
            skipped_trade = (
                Trade("id", current_time, TraderDetails("test_area", strategy.owner.uuid),
                      TraderDetails("parent_area", "parent_area_uuid"), bid=bid,
                      fee_price=0.23, traded_energy=1, trade_price=1))

            strategy.event_bid_traded(market_id=market.id, bid_trade=skipped_trade)
            call_args = strategy.redis.aggregator.add_batch_trade_event.call_args_list
            assert call_args == []

            published_trade = (
                Trade("id", current_time, TraderDetails("parent_area", "parent_area_uuid"),
                      TraderDetails("test_area", strategy.owner.uuid), fee_price=0.23, bid=bid,
                      traded_energy=1, trade_price=1))
            strategy.event_bid_traded(market_id=market.id, bid_trade=published_trade)
            assert (strategy.redis.aggregator.add_batch_trade_event.call_args_list[0][0][0] ==
                    self.area.uuid)
        else:
            offer = Offer("offer_id", now(), 20, 1.0,
                          TraderDetails("test_area", strategy.owner.uuid))
            strategy.offers.post(offer, market.id)
            skipped_trade = (
                Trade("id", current_time, TraderDetails("parent_area", "parent_area_uuid"),
                      TraderDetails("test_area", strategy.owner.uuid), offer=offer,
                      fee_price=0.23, traded_energy=1, trade_price=1))
            strategy.offers.sold_offer(offer, market.id)

            strategy.event_offer_traded(market_id=market.id, trade=skipped_trade)
            call_args = strategy.redis.aggregator.add_batch_trade_event.call_args_list
            assert call_args == []

            published_trade = (
                Trade("id", current_time, TraderDetails("test_area", strategy.owner.uuid),
                      TraderDetails("parent_area", "parent_area_uuid"), offer=offer,
                      fee_price=0.23, traded_energy=1, trade_price=1))
            strategy.event_offer_traded(market_id=market.id, trade=published_trade)
            assert (strategy.redis.aggregator.add_batch_trade_event.call_args_list[0][0][0] ==
                    self.area.uuid)

    def test_device_info_dict_for_load_strategy_reports_required_energy(self):
        strategy = LoadHoursExternalStrategy(100)
        self._create_and_activate_strategy_area(strategy)
        strategy.state._energy_requirement_Wh[strategy.spot_market.time_slot] = 0.987
        assert strategy._device_info_dict["energy_requirement_kWh"] == 0.000987

    def test_device_info_dict_for_pv_strategy_reports_available_energy(self):
        strategy = PVExternalStrategy(2, capacity_kW=0.16)
        self._create_and_activate_strategy_area(strategy)
        strategy.state._available_energy_kWh[strategy.spot_market.time_slot] = 1.123
        assert strategy._device_info_dict["available_energy_kWh"] == 1.123

    def test_device_info_dict_for_storage_strategy_reports_battery_stats(self):
        strategy = StorageExternalStrategy(battery_capacity_kWh=0.5)
        self._create_and_activate_strategy_area(strategy)
        strategy.state.energy_to_sell_dict[strategy.spot_market.time_slot] = 0.02
        strategy.state.energy_to_buy_dict[strategy.spot_market.time_slot] = 0.03
        strategy.state._used_storage = 0.01
        assert strategy._device_info_dict["energy_to_sell"] == 0.02
        assert strategy._device_info_dict["energy_to_buy"] == 0.03
        assert strategy._device_info_dict["used_storage"] == 0.01
        assert strategy._device_info_dict["free_storage"] == 0.49

    @parameterized.expand([
        [LoadHoursExternalStrategy(100)],
        [PVExternalStrategy(2, capacity_kW=0.16)],
        [StorageExternalStrategy()]
    ])
    def test_register_device(self, strategy):
        config = GlobalConfig
        config.external_redis_communicator = Mock()
        device = Area(name="area", config=config, strategy=strategy)
        area = Area(name="test_area", config=config, children=[device])
        device.strategy.owner = device
        device.strategy.area = area
        device.strategy.event_activate()

        payload = {"data": json.dumps({"transaction_id": transaction_id})}
        assert device.strategy.connected is False
        device.strategy._register(payload)
        device.strategy._update_connection_status()
        assert device.strategy.connected is True
        device.strategy._unregister(payload)
        device.strategy._update_connection_status()
        assert device.strategy.connected is False

        payload = {"data": json.dumps({"transaction_id": None})}
        with pytest.raises(ValueError):
            device.strategy._register(payload)
        with pytest.raises(ValueError):
            device.strategy._unregister(payload)

    @parameterized.expand([
        [LoadHoursExternalStrategy(100)],
        [PVExternalStrategy(2, capacity_kW=0.16)],
        [StorageExternalStrategy()]
    ])
    def test_get_state(self, strategy):
        strategy.state.get_state = MagicMock(return_value={"available_energy": 500})
        strategy.connected = True
        strategy._use_template_strategy = True
        current_state = strategy.get_state()
        assert current_state["connected"] is True
        assert current_state["use_template_strategy"] is True
        assert current_state["available_energy"] == 500

    @parameterized.expand([
        [LoadHoursExternalStrategy(100)],
        [PVExternalStrategy(2, capacity_kW=0.16)],
        [StorageExternalStrategy()]
    ])
    def test_restore_state(self, strategy):
        strategy.state.restore_state = MagicMock()
        strategy.connected = True
        strategy._is_registered = True
        strategy._use_template_strategy = True
        state_dict = {
            "connected": False,
            "use_template_strategy": False,
            "available_energy": 123
        }
        strategy.restore_state(state_dict)
        assert strategy.connected is False
        assert strategy._is_registered is False
        assert strategy._use_template_strategy is False
        strategy.state.restore_state.assert_called_once_with(state_dict)

    @staticmethod
    @pytest.mark.parametrize("strategy", [
        LoadHoursExternalStrategy(100),
        PVExternalStrategy(2, capacity_kW=0.16),
        StorageExternalStrategy()
    ])
    def test_get_market_from_cmd_arg_returns_spot_market_if_arg_missing(strategy):
        strategy.area = Mock()
        strategy.area.spot_market = Mock()
        market = strategy._get_market_from_command_argument({})
        assert market == strategy.area.spot_market

    @staticmethod
    @pytest.mark.parametrize("strategy", [
        LoadHoursExternalStrategy(100),
        PVExternalStrategy(2, capacity_kW=0.16),
        StorageExternalStrategy()
    ])
    def test_get_market_from_cmd_arg_returns_spot_market(strategy):
        strategy.area = Mock()
        strategy.area.spot_market = Mock()
        time_slot = format_datetime(now())
        market_mock = Mock()
        strategy.area.get_market = MagicMock(return_value=market_mock)
        market = strategy._get_market_from_command_argument({"time_slot": time_slot})
        assert market == market_mock

    @staticmethod
    @pytest.mark.parametrize("strategy", [
        LoadHoursExternalStrategy(100),
        PVExternalStrategy(2, capacity_kW=0.16),
        StorageExternalStrategy()
    ])
    def test_get_market_from_cmd_arg_returns_settlement_market(strategy):
        strategy.area = Mock()
        strategy.area.spot_market = Mock()
        time_slot = format_datetime(now())
        market_mock = Mock()
        strategy.area.get_market = MagicMock(return_value=None)
        strategy.area.get_settlement_market = MagicMock(return_value=market_mock)
        market = strategy._get_market_from_command_argument({"time_slot": time_slot})
        assert market == market_mock

    @staticmethod
    @pytest.mark.parametrize("strategy", [
        LoadHoursExternalStrategy(100),
        LoadProfileExternalStrategy(),
        PVExternalStrategy(2, capacity_kW=0.16),
        PVUserProfileExternalStrategy(),
        PVPredefinedExternalStrategy(),
        StorageExternalStrategy()])
    def test_filter_degrees_of_freedom_arguments(strategy):
        """Degrees of Freedom are correctly filtered in all external strategies."""
        order_arguments = {
            "type": "bid", "energy": 0.025, "price": 30, "replace_existing": True,
            "attributes": {"energy_type": "PV"}, "requirements": [{"price": 12}],
            "timeslot": None, "transaction_id": "some-id"}

        strategy.area = Mock(spec=Area)
        # Arguments are preserved when required
        type(strategy.simulation_config).enable_degrees_of_freedom = PropertyMock(
            return_value=True)
        result = strategy.filter_degrees_of_freedom_arguments(order_arguments)
        assert result == (order_arguments, [])

        # Arguments are removed when required
        type(strategy.simulation_config).enable_degrees_of_freedom = PropertyMock(
            return_value=False)
        result = strategy.filter_degrees_of_freedom_arguments(order_arguments)
        assert result == ({
            "type": "bid", "energy": 0.025, "price": 30, "replace_existing": True,
            "timeslot": None, "transaction_id": "some-id"},
            ["requirements", "attributes"])


class TestForecastRelatedFeatures:

    @staticmethod
    @pytest.mark.parametrize("ext_strategy_fixture", [
        LoadHoursForecastExternalStrategy(),
        LoadProfileForecastExternalStrategy(),
        PVForecastExternalStrategy()], indirect=True)
    def test_set_energy_forecast_succeeds(ext_strategy_fixture):
        arguments = {"transaction_id": transaction_id,
                     "energy_forecast": {now().format(gsy_e.constants.DATE_TIME_FORMAT): 1}}
        payload = {"data": json.dumps(arguments)}
        assert ext_strategy_fixture.pending_requests == deque([])
        ext_strategy_fixture._set_energy_forecast(payload)
        assert len(ext_strategy_fixture.pending_requests) > 0
        assert (ext_strategy_fixture.pending_requests ==
                deque([IncomingRequest("set_energy_forecast", arguments,
                                       ext_strategy_fixture.channel_names.energy_forecast)]))

    @staticmethod
    @pytest.mark.parametrize("ext_strategy_fixture", [
        LoadHoursForecastExternalStrategy(),
        LoadProfileForecastExternalStrategy(),
        PVForecastExternalStrategy()], indirect=True)
    def test_set_energy_forecast_fails_for_wrong_payload(ext_strategy_fixture):
        ext_strategy_fixture.redis.publish_json = Mock()
        ext_strategy_fixture.pending_requests = deque([])
        payload = {"data": json.dumps({"transaction_id": transaction_id})}
        ext_strategy_fixture._set_energy_forecast(payload)
        ext_strategy_fixture.redis.publish_json.assert_called_with(
            ext_strategy_fixture.channel_names.energy_forecast,
            {"command": "set_energy_forecast",
             "error": "Incorrect set_energy_forecast request. "
                      "Available parameters: (energy_forecast).",
             "transaction_id": transaction_id})
        assert len(ext_strategy_fixture.pending_requests) == 0

    @staticmethod
    @pytest.mark.parametrize("ext_strategy_fixture", [
        LoadHoursForecastExternalStrategy(),
        LoadProfileForecastExternalStrategy(),
        PVForecastExternalStrategy()], indirect=True)
    def test_set_energy_measurement_succeeds(ext_strategy_fixture):
        arguments = {"transaction_id": transaction_id,
                     "energy_measurement": {now().format(gsy_e.constants.DATE_TIME_FORMAT): 1}}
        payload = {"data": json.dumps(arguments)}
        assert ext_strategy_fixture.pending_requests == deque([])
        ext_strategy_fixture._set_energy_measurement(payload)
        assert len(ext_strategy_fixture.pending_requests) > 0
        assert (ext_strategy_fixture.pending_requests ==
                deque([IncomingRequest("set_energy_measurement", arguments,
                                       ext_strategy_fixture.channel_names.energy_measurement)]))

    @pytest.mark.parametrize("ext_strategy_fixture", [
        LoadHoursForecastExternalStrategy(),
        LoadProfileForecastExternalStrategy(),
        PVForecastExternalStrategy()], indirect=True)
    def test_set_energy_measurement_fails_for_wrong_payload(self, ext_strategy_fixture):
        ext_strategy_fixture.redis.publish_json = Mock()
        ext_strategy_fixture.pending_requests = deque([])
        payload = {"data": json.dumps({"transaction_id": transaction_id})}
        ext_strategy_fixture._set_energy_measurement(payload)
        ext_strategy_fixture.redis.publish_json.assert_called_with(
            ext_strategy_fixture.channel_names.energy_measurement,
            {"command": "set_energy_measurement",
             "error": "Incorrect set_energy_measurement request. "
                      "Available parameters: (energy_measurement).",
             "transaction_id": transaction_id})
        assert len(ext_strategy_fixture.pending_requests) == 0

    @pytest.mark.parametrize("ext_strategy_fixture", [
        LoadHoursForecastExternalStrategy(),
        LoadProfileForecastExternalStrategy(),
        PVForecastExternalStrategy()], indirect=True)
    def test_set_energy_forecast_impl_succeeds(self, ext_strategy_fixture):
        ext_strategy_fixture.redis.publish_json = Mock()
        arguments = {"transaction_id": transaction_id,
                     "energy_forecast": {now().format(gsy_e.constants.DATE_TIME_FORMAT): 1}}
        response_channel = "response_channel"
        ext_strategy_fixture._set_energy_forecast_impl(arguments, response_channel)
        ext_strategy_fixture.redis.publish_json.assert_called_once_with(
            response_channel, {"command": "set_energy_forecast",
                               "status": "ready",
                               "transaction_id": arguments["transaction_id"]})

    @pytest.mark.parametrize("ext_strategy_fixture", [
        LoadHoursForecastExternalStrategy(),
        LoadProfileForecastExternalStrategy(),
        PVForecastExternalStrategy()], indirect=True)
    def test_set_energy_forecast_impl_fails_for_wrong_time_format(self, ext_strategy_fixture):
        ext_strategy_fixture.redis.publish_json.reset_mock()
        response_channel = "response_channel"
        arguments = {"transaction_id": transaction_id,
                     "energy_forecast": {"wrong:time:format": 1}}
        ext_strategy_fixture._set_energy_forecast_impl(arguments, response_channel)
        error_message = ("Error when handling _set_energy_forecast_impl "
                         f"on area {ext_strategy_fixture.device.name}. Arguments: {arguments}")
        ext_strategy_fixture.redis.publish_json.assert_called_once_with(
            response_channel, {"command": "set_energy_forecast",
                               "status": "error",
                               "transaction_id": arguments["transaction_id"],
                               "error_message": error_message})

    @pytest.mark.parametrize("ext_strategy_fixture", [
        LoadHoursForecastExternalStrategy(),
        LoadProfileForecastExternalStrategy(),
        PVForecastExternalStrategy()], indirect=True)
    def test_set_energy_forecast_impl_fails_for_negative_energy(self, ext_strategy_fixture):
        ext_strategy_fixture.redis.publish_json.reset_mock()
        response_channel = "response_channel"
        arguments = {"transaction_id": transaction_id,
                     "energy_forecast": {now().format(gsy_e.constants.DATE_TIME_FORMAT): -1}}
        ext_strategy_fixture._set_energy_forecast_impl(arguments, response_channel)
        error_message = ("Error when handling _set_energy_forecast_impl "
                         f"on area {ext_strategy_fixture.device.name}. Arguments: {arguments}")
        ext_strategy_fixture.redis.publish_json.assert_called_once_with(
            response_channel, {"command": "set_energy_forecast",
                               "status": "error",
                               "transaction_id": arguments["transaction_id"],
                               "error_message": error_message})

    @pytest.mark.parametrize("ext_strategy_fixture", [
        LoadHoursForecastExternalStrategy(),
        LoadProfileForecastExternalStrategy(),
        PVForecastExternalStrategy()], indirect=True)
    def test_set_energy_measurement_impl_succeeds(self, ext_strategy_fixture):
        # test successful call of set_energy_measurement_impl:
        ext_strategy_fixture.redis.publish_json = Mock()
        arguments = {"transaction_id": transaction_id,
                     "energy_measurement": {now().format(gsy_e.constants.DATE_TIME_FORMAT): 1}}
        response_channel = "response_channel"
        ext_strategy_fixture._set_energy_measurement_impl(arguments, response_channel)
        ext_strategy_fixture.redis.publish_json.assert_called_once_with(
            response_channel, {"command": "set_energy_measurement",
                               "status": "ready",
                               "transaction_id": arguments["transaction_id"]})

    @pytest.mark.parametrize("ext_strategy_fixture", [
        LoadHoursForecastExternalStrategy(),
        LoadProfileForecastExternalStrategy(),
        PVForecastExternalStrategy()], indirect=True)
    def test_set_energy_measurement_impl_fails_for_wrong_time_format(self, ext_strategy_fixture):
        response_channel = "response_channel"
        ext_strategy_fixture.redis.publish_json.reset_mock()
        arguments = {"transaction_id": transaction_id,
                     "energy_measurement": {"wrong:time:format": 1}}
        ext_strategy_fixture._set_energy_measurement_impl(arguments, response_channel)
        error_message = ("Error when handling _set_energy_measurement_impl "
                         f"on area {ext_strategy_fixture.device.name}. Arguments: {arguments}")
        ext_strategy_fixture.redis.publish_json.assert_called_once_with(
            response_channel, {"command": "set_energy_measurement",
                               "status": "error",
                               "transaction_id": arguments["transaction_id"],
                               "error_message": error_message})

    @pytest.mark.parametrize("ext_strategy_fixture", [
        LoadHoursForecastExternalStrategy(),
        LoadProfileForecastExternalStrategy(),
        PVForecastExternalStrategy()], indirect=True)
    def test_set_energy_measurement_impl_fails_for_negative_energy(self, ext_strategy_fixture):
        response_channel = "response_channel"
        ext_strategy_fixture.redis.publish_json.reset_mock()
        arguments = {"transaction_id": transaction_id,
                     "energy_measurement": {now().format(gsy_e.constants.DATE_TIME_FORMAT): -1}}
        ext_strategy_fixture._set_energy_measurement_impl(arguments, response_channel)
        error_message = ("Error when handling _set_energy_measurement_impl "
                         f"on area {ext_strategy_fixture.device.name}. Arguments: {arguments}")
        ext_strategy_fixture.redis.publish_json.assert_called_once_with(
            response_channel, {"command": "set_energy_measurement",
                               "status": "error",
                               "transaction_id": arguments["transaction_id"],
                               "error_message": error_message})

    @pytest.mark.parametrize("ext_strategy", [
        LoadHoursForecastExternalStrategy(),
        LoadProfileForecastExternalStrategy(),
        PVForecastExternalStrategy()])
    @pytest.mark.parametrize("command_name", ["set_energy_forecast", "set_energy_measurement"])
    def test_set_device_energy_data_aggregator_succeeds(self, ext_strategy, command_name):
        ext_strategy.owner = Mock()
        device_uuid = str(uuid.uuid4())
        ext_strategy.owner.uuid = device_uuid
        if command_name == "set_energy_forecast":
            energy_buffer = ext_strategy.energy_forecast_buffer
            argument_name = "energy_forecast"
        elif command_name == "set_energy_measurement":
            energy_buffer = ext_strategy.energy_measurement_buffer
            argument_name = "energy_measurement"
        else:
            assert False

        return_value = ext_strategy.trigger_aggregator_commands(
            {
                "type": command_name,
                argument_name: {"2021-03-04T12:00": 1234.0}
            }
        )
        assert len(energy_buffer.values()) == 1
        assert list(energy_buffer.values())[0] == 1234.0
        assert list(energy_buffer.keys())[0] == datetime(2021, 3, 4, 12, 00)
        assert return_value["command"] == command_name
        assert return_value["status"] == "ready"
        assert return_value["area_uuid"] == device_uuid
        assert command_name in return_value
        assert argument_name in return_value[command_name]
        assert list(return_value[command_name][argument_name].values())[0] == 1234.0


class TestAreaExternalConnectionManager:
    """Test the AreaExternalConnectionManager class."""
    def test_register(self):
        """Test the register method of AreaExternalConnectionManager."""
        redis_communicator = MagicMock()
        # is_connected=True
        assert ExternalStrategyConnectionManager.register(
            redis_communicator, "channel1", is_connected=True,
            transaction_id="transaction1", area_uuid="area1") is True
        redis_communicator.publish_json.assert_not_called()

        # is_connected=False
        response_channel = "channel1"
        assert ExternalStrategyConnectionManager.register(
            redis_communicator, response_channel, is_connected=False,
            transaction_id="transaction1", area_uuid="area1") is True
        redis_communicator.publish_json.assert_called_once_with(
            response_channel,
            {"command": "register", "status": "ready", "registered": True,
             "transaction_id": "transaction1", "device_uuid": "area1"}
        )

        # Exception raised
        redis_communicator.reset_mock()
        redis_communicator.publish_json.side_effect = RedisError
        assert ExternalStrategyConnectionManager.register(
            redis_communicator, "channel1", is_connected=False,
            transaction_id="transaction1", area_uuid="area1") is False

    @patch("gsy_e.models.strategy.external_strategies.ExternalStrategyConnectionManager."
           "check_for_connected_and_reply")
    def test_unregister(self, check_for_connected_mock):
        """Test the unregister method of AreaExternalConnectionManager."""
        redis_communicator = MagicMock()

        # is_connected=False
        check_for_connected_mock.return_value = False
        assert ExternalStrategyConnectionManager.unregister(
            redis_communicator, "channel1", is_connected=False,
            transaction_id="transaction1") is False
        redis_communicator.publish_json.assert_not_called()

        # is_connected=True
        check_for_connected_mock.return_value = True
        response_channel = "channel1"
        assert ExternalStrategyConnectionManager.unregister(
            redis_communicator, response_channel, is_connected=True,
            transaction_id="transaction1") is False
        redis_communicator.publish_json.assert_called_once_with(
            response_channel,
            {"command": "unregister", "status": "ready", "unregistered": True,
             "transaction_id": "transaction1"}
        )

        # Exception raised
        redis_communicator.reset_mock()
        redis_communicator.publish_json.side_effect = RedisError
        assert ExternalStrategyConnectionManager.unregister(
            redis_communicator, "channel1", is_connected=False,
            transaction_id="transaction1") is False

    @staticmethod
    def test_check_for_connected_and_reply():
        """Test the check_for_connected_and_reply method of AreaExternalConnectionManager."""
        redis_communicator = MagicMock()

        assert ExternalStrategyConnectionManager.check_for_connected_and_reply(
            redis_communicator, "channel1", is_connected=True) is True
        redis_communicator.publish_json.assert_not_called()

        assert ExternalStrategyConnectionManager.check_for_connected_and_reply(
            redis_communicator, "channel1", is_connected=False) is False
        redis_communicator.publish_json.assert_called_once_with(
            "channel1",
            {"status": "error",
             "error_message": "Client should be registered in order to access this area."}
        )
