from pendulum import Interval
from unittest.mock import MagicMock
import unittest
from d3a.models.area import Area
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.config import SimulationConfig


class TestAreaClass(unittest.TestCase):

    def setUp(self):
        self.appliance = MagicMock(spec=SimpleAppliance)
        self.strategy = MagicMock(spec=StorageStrategy)
        self.config = MagicMock(spec=SimulationConfig)
        self.config.slot_length = Interval(minutes=15)
        self.config.tick_length = Interval(seconds=15)
        self.area = Area("test_area", None, self.strategy, self.appliance, self.config, None)
        self.area.parent = self.area
        self.area.children = [self.area]

    def tearDown(self):
        pass

    def test_markets_are_cycled_according_to_market_count(self):
        for i in range(2, 100):
            self.config.market_count = i
            self.area._cycle_markets(False, False)
            assert len(self.area.markets) == i
