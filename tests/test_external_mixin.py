import unittest
import uuid
import json
from unittest.mock import MagicMock
from parameterized import parameterized
from pendulum import now
from d3a.models.area import Area
from d3a.models.strategy.external_strategies.load import LoadHoursExternalStrategy
from d3a.models.strategy.external_strategies.pv import PVExternalStrategy
from d3a.models.strategy.external_strategies.storage import StorageExternalStrategy
import d3a.models.strategy.external_strategies
from d3a.models.market.market_structures import Trade, Offer

d3a.models.strategy.external_strategies.ResettableCommunicator = MagicMock


class TestExternalMixin(unittest.TestCase):

    def _create_and_activate_strategy_area(self, strategy):
        self.config = MagicMock()
        self.config.max_panel_power_W = 160
        self.area = Area(name="test_area", config=self.config, strategy=strategy)
        parent = Area(name="parent_area", children=[self.area])
        parent.activate()
        strategy.connected = True
        market = MagicMock()
        parent.get_future_market_from_id = lambda _: market
        self.area.get_future_market_from_id = lambda _: market

    def test_dispatch_tick_frequency_gets_calculated_correctly(self):
        self.external_strategy = LoadHoursExternalStrategy(100)
        self._create_and_activate_strategy_area(self.external_strategy)
        d3a.models.strategy.external_strategies.DISPATCH_EVENT_TICK_FREQUENCY_PERCENT = 20
        self.config.ticks_per_slot = 90
        assert self.external_strategy._dispatch_tick_frequency == 18
        self.config.ticks_per_slot = 10
        assert self.external_strategy._dispatch_tick_frequency == 2
        self.config.ticks_per_slot = 100
        assert self.external_strategy._dispatch_tick_frequency == 20
        self.config.ticks_per_slot = 99
        assert self.external_strategy._dispatch_tick_frequency == 19
        d3a.models.strategy.external_strategies.DISPATCH_EVENT_TICK_FREQUENCY_PERCENT = 50
        self.config.ticks_per_slot = 90
        assert self.external_strategy._dispatch_tick_frequency == 45
        self.config.ticks_per_slot = 10
        assert self.external_strategy._dispatch_tick_frequency == 5
        self.config.ticks_per_slot = 100
        assert self.external_strategy._dispatch_tick_frequency == 50
        self.config.ticks_per_slot = 99
        assert self.external_strategy._dispatch_tick_frequency == 49

    @parameterized.expand([
        [LoadHoursExternalStrategy(100)],
        [PVExternalStrategy(2, max_panel_power_W=160)],
        [StorageExternalStrategy()]
    ])
    def test_dispatch_event_tick_to_external_agent(self, strategy):
        d3a.models.strategy.external_strategies.DISPATCH_EVENT_TICK_FREQUENCY_PERCENT = 20
        self._create_and_activate_strategy_area(strategy)
        self.config.ticks_per_slot = 90
        assert strategy._dispatch_tick_frequency == 18
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
        assert strategy.redis.publish_json.call_args_list[0][0][1] == \
            {'device_info': strategy._device_info_dict, 'event': 'tick', 'slot_completion': '20%'}
        strategy.redis.reset_mock()
        strategy.redis.publish_json.reset_mock()
        self.area.current_tick = 35
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.publish_json.assert_not_called()
        self.area.current_tick = 36
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.publish_json.assert_called_once()
        assert strategy.redis.publish_json.call_args_list[0][0][0] == "test_area/events/tick"
        assert strategy.redis.publish_json.call_args_list[0][0][1] == \
            {'device_info': strategy._device_info_dict, 'event': 'tick', 'slot_completion': '40%'}

    @parameterized.expand([
        [LoadHoursExternalStrategy(100)],
        [PVExternalStrategy(2, max_panel_power_W=160)],
        [StorageExternalStrategy()]
    ])
    def test_dispatch_event_trade_to_external_agent(self, strategy):
        self._create_and_activate_strategy_area(strategy)
        current_time = now()
        trade = Trade('id', current_time, Offer('id', 20, 1.0, 'ParentArea'),
                      'FakeArea', 'FakeArea')
        strategy.event_trade(market_id="test_market", trade=trade)
        assert strategy.redis.publish_json.call_args_list[0][0][0] == "test_area/events/trade"
        call_args = strategy.redis.publish_json.call_args_list[0][0][1]
        assert call_args['id'] == trade.id
        assert call_args['time'] == current_time.isoformat()
        assert call_args['seller'] == trade.seller
        assert call_args['buyer'] == trade.buyer
        assert call_args['offer'] == trade.offer.to_JSON_string()
        assert call_args['device_info'] == strategy._device_info_dict

    def test_device_info_dict_for_load_strategy_reports_required_energy(self):
        strategy = LoadHoursExternalStrategy(100)
        self._create_and_activate_strategy_area(strategy)
        strategy.energy_requirement_Wh[strategy.market.time_slot] = 0.987
        assert strategy._device_info_dict["energy_requirement_kWh"] == 0.000987

    def test_device_info_dict_for_pv_strategy_reports_available_energy(self):
        strategy = PVExternalStrategy(2, max_panel_power_W=160)
        self._create_and_activate_strategy_area(strategy)
        strategy.state.available_energy_kWh[strategy.market.time_slot] = 1.123
        assert strategy._device_info_dict["available_energy_kWh"] == 1.123

    def test_device_info_dict_for_storage_strategy_reports_battery_stats(self):
        strategy = StorageExternalStrategy(battery_capacity_kWh=0.5)
        self._create_and_activate_strategy_area(strategy)
        strategy.state.energy_to_sell_dict[strategy.market.time_slot] = 0.02
        strategy.state.energy_to_buy_dict[strategy.market.time_slot] = 0.03
        strategy.state._used_storage = 0.01
        assert strategy._device_info_dict["energy_to_sell"] == 0.02
        assert strategy._device_info_dict["energy_to_buy"] == 0.03
        assert strategy._device_info_dict["used_storage"] == 0.01
        assert strategy._device_info_dict["free_storage"] == 0.49

    @parameterized.expand([
        [LoadHoursExternalStrategy(100)],
        [PVExternalStrategy(2, max_panel_power_W=160)],
        [StorageExternalStrategy()]
    ])
    def test_register_device(self, strategy):
        self.config = MagicMock()
        self.device = Area(name="test_area", config=self.config, strategy=strategy)
        payload = {"data": json.dumps({"transaction_id": str(uuid.uuid4())})}
        self.device.strategy.owner = self.device
        assert self.device.strategy.connected is False
        self.device.strategy._register(payload)
        self.device.strategy.register_on_market_cycle()
        assert self.device.strategy.connected is True
        self.device.strategy._unregister(payload)
        self.device.strategy.register_on_market_cycle()
        assert self.device.strategy.connected is False

        payload = {"data": json.dumps({"transaction_id": None})}
        with self.assertRaises(ValueError):
            self.device.strategy._register(payload)
        with self.assertRaises(ValueError):
            self.device.strategy._unregister(payload)
