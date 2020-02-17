import unittest
from unittest.mock import MagicMock
from parameterized import parameterized
from d3a.models.area import Area
from d3a.models.strategy.external_strategies.load import LoadHoursExternalStrategy
from d3a.models.strategy.external_strategies.pv import PVExternalStrategy
import d3a.models.strategy.external_strategies

d3a.models.strategy.external_strategies.ResettableCommunicator = MagicMock


class TestExternalMixin(unittest.TestCase):

    def test_dispatch_tick_frequency_gets_calculated_correctly(self):
        self.external_strategy = LoadHoursExternalStrategy(100)
        config = MagicMock()
        self.area = Area(name="test_area", config=config, strategy=self.external_strategy)
        self.parent = Area(name="parent_area", children=[self.area])
        self.parent.activate()
        self.external_strategy.connected = True
        config.ticks_per_slot = 90
        assert self.external_strategy._dispatch_tick_frequency == 18
        config.ticks_per_slot = 10
        assert self.external_strategy._dispatch_tick_frequency == 2
        config.ticks_per_slot = 100
        assert self.external_strategy._dispatch_tick_frequency == 20
        config.ticks_per_slot = 99
        assert self.external_strategy._dispatch_tick_frequency == 19
        d3a.models.strategy.external_strategies.DISPATCH_EVENT_TICK_FREQUENCY_PERCENT = 50
        config.ticks_per_slot = 90
        assert self.external_strategy._dispatch_tick_frequency == 45
        config.ticks_per_slot = 10
        assert self.external_strategy._dispatch_tick_frequency == 5
        config.ticks_per_slot = 100
        assert self.external_strategy._dispatch_tick_frequency == 50
        config.ticks_per_slot = 99
        assert self.external_strategy._dispatch_tick_frequency == 49

    @parameterized.expand([
        [LoadHoursExternalStrategy(100)],
        [PVExternalStrategy(2, max_panel_power_W=160)]
    ])
    def test_dispatch_event_tick_to_external_agent(self, strategy):
        config = MagicMock()
        config.max_panel_power_W = 160
        area = Area(name="test_area", config=config, strategy=strategy)
        parent = Area(name="parent_area", children=[area])
        parent.activate()
        strategy.connected = True
        config.ticks_per_slot = 90
        assert strategy._dispatch_tick_frequency == 18
        area.current_tick = 1
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.publish_json.assert_not_called()
        area.current_tick = 17
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.publish_json.assert_not_called()
        area.current_tick = 18
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.publish_json.assert_called_once()
        assert strategy.redis.publish_json.call_args_list[0][0][0] == "test_area/tick"
        assert strategy.redis.publish_json.call_args_list[0][0][1] == {'slot_completion': '20%'}
        strategy.redis.reset_mock()
        strategy.redis.publish_json.reset_mock()
        area.current_tick = 35
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.publish_json.assert_not_called()
        area.current_tick = 36
        strategy._dispatch_event_tick_to_external_agent()
        strategy.redis.publish_json.assert_called_once()
        assert strategy.redis.publish_json.call_args_list[0][0][0] == "test_area/tick"
        assert strategy.redis.publish_json.call_args_list[0][0][1] == {'slot_completion': '40%'}
