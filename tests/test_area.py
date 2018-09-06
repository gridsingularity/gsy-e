from pendulum import Interval, Pendulum
from collections import OrderedDict
from unittest.mock import MagicMock
import unittest
from d3a.models.area import Area
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.config import SimulationConfig
from d3a.models.market import Market, Offer


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
        self.area._bc = False
        for i in range(2, 100):
            self.config.market_count = i
            self.area._cycle_markets(False, False)
            assert len(self.area.markets) == i

    def test_market_with_most_expensive_offer(self):
        m1 = MagicMock(spec=Market)
        o1 = MagicMock(spec=Offer)
        o1.price = 12
        o1.energy = 1
        m2 = MagicMock(spec=Market)
        o2 = MagicMock(spec=Offer)
        o2.price = 12
        o2.energy = 1
        m3 = MagicMock(spec=Market)
        o3 = MagicMock(spec=Offer)
        o3.price = 12
        o3.energy = 1
        markets = OrderedDict()
        markets[Pendulum(2018, 1, 1, 12, 0, 0)] = m1
        markets[Pendulum(2018, 1, 1, 12, 15, 0)] = m2
        markets[Pendulum(2018, 1, 1, 12, 30, 0)] = m3
        self.area.markets = markets
        m1.sorted_offers = [o1, o1]
        m2.sorted_offers = [o2, o2]
        m3.sorted_offers = [o3, o3]
        assert self.area.market_with_most_expensive_offer is m1
        o1.price = 19
        o2.price = 20
        o3.price = 18
        assert self.area.market_with_most_expensive_offer is m2
        o1.price = 18
        o2.price = 19
        o3.price = 20
        assert self.area.market_with_most_expensive_offer is m3
