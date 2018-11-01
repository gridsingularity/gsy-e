from pendulum import duration, DateTime
from collections import OrderedDict
from unittest.mock import MagicMock
import unittest
from d3a.models.area import Area
from d3a.models.area.markets import AreaMarkets
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.config import SimulationConfig
from d3a.models.market import Market
from d3a.models.market.market_structures import Offer
from d3a.models.strategy.const import ConstSettings
from d3a.device_registry import DeviceRegistry


class TestAreaClass(unittest.TestCase):

    def setUp(self):
        ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
        DeviceRegistry.REGISTRY = {
            "H1 General Load": (33, 35),
            "H2 General Load": (33, 35),
            "H1 Storage1": (23, 25),
            "H1 Storage2": (23, 25),
        }

        self.appliance = MagicMock(spec=SimpleAppliance)
        self.strategy = MagicMock(spec=StorageStrategy)
        self.config = MagicMock(spec=SimulationConfig)
        self.config.slot_length = duration(minutes=15)
        self.config.tick_length = duration(seconds=15)
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
            assert len(self.area.all_markets) == i

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
        markets[DateTime(2018, 1, 1, 12, 0, 0)] = m1
        markets[DateTime(2018, 1, 1, 12, 15, 0)] = m2
        markets[DateTime(2018, 1, 1, 12, 30, 0)] = m3
        self.area._markets = MagicMock(spec=AreaMarkets)
        self.area._markets.markets = markets
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

    def test_cycle_markets(self):
        self.area = Area(name="Street", children=[Area(name="House")])
        self.area.parent = Area(name="GRID")
        self.area.config.market_count = 5
        self.area.activate()
        assert len(self.area.all_markets) == 5

        assert len(self.area.balancing_markets) == 5
        self.area.current_tick = 900
        self.area.tick()
        assert len(self.area.past_markets) == 1
        assert len(self.area.past_balancing_markets) == 1
        assert len(self.area.all_markets) == 5
        assert len(self.area.balancing_markets) == 5
