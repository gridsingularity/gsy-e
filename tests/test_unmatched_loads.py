from pendulum import Interval, Pendulum
from d3a.export_unmatched_loads import export_unmatched_loads
from unittest.mock import MagicMock
import unittest
from d3a.models.area import Area
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.state import LoadState
from d3a.models.strategy.permanent import PermanentLoadStrategy
from d3a.models.config import SimulationConfig
from d3a.models.market import Market


class TestUnmatchedLoad(unittest.TestCase):

    def setUp(self):
        self.appliance = MagicMock(spec=SimpleAppliance)
        self.strategy1 = MagicMock(spec=LoadHoursStrategy)
        self.strategy1.state = MagicMock(spec=LoadState)
        self.strategy1.state.desired_energy = {}
        self.strategy2 = MagicMock(spec=PermanentLoadStrategy)
        self.config = MagicMock(spec=SimulationConfig)
        self.config.slot_length = Interval(minutes=15)
        self.config.tick_length = Interval(seconds=15)
        self.area1 = Area("load1", None, self.strategy1, self.appliance, self.config, None)
        self.area2 = Area("load2", None, self.strategy2, self.appliance, self.config, None)

    def tearDown(self):
        pass

    def test_export_unmatched_loads_is_reported_correctly_for_all_loads_matched(self):
        house1 = Area("House1", [self.area1, self.area2])
        for i in range(1, 11):
            timeslot = Pendulum(2018, 1, 1, 12+i, 0, 0)
            mock_market = MagicMock(spec=Market)
            mock_market.traded_energy = {"load1":  101}
            self.strategy1.state.desired_energy[timeslot] = 100
            self.area1.past_markets[timeslot] = mock_market

            mock_market2 = MagicMock(spec=Market)
            mock_market2.traded_energy = {"load2": 101}
            self.strategy2.energy = 100
            self.area2.past_markets[timeslot] = mock_market2

            mock_market3 = MagicMock(spec=Market)
            mock_market3.traded_energy = {"load1":  101, "load2": 101}
            house1.past_markets[timeslot] = mock_market3
        self.grid = Area("Grid", [house1])

        unmatched_loads = export_unmatched_loads(self.grid)
        assert unmatched_loads["unmatched_load_count"] == 0
        assert unmatched_loads["all_loads_met"]

    def test_export_unmatched_loads_is_reported_correctly_for_all_loads_unmatched(self):
        house1 = Area("House1", [self.area1, self.area2])
        for i in range(1, 11):
            timeslot = Pendulum(2018, 1, 1, 12+i, 0, 0)
            mock_market = MagicMock(spec=Market)
            mock_market.traded_energy = {"load1":  90}
            self.strategy1.state.desired_energy[timeslot] = 100
            self.area1.past_markets[timeslot] = mock_market

            mock_market = MagicMock(spec=Market)
            mock_market.traded_energy = {"load2": 70}
            self.strategy2.energy = 100
            self.area2.past_markets[timeslot] = mock_market

            mock_market3 = MagicMock(spec=Market)
            mock_market3.traded_energy = {"load1":  100, "load2": 100}
            house1.past_markets[timeslot] = mock_market3
        self.grid = Area("Grid", [house1])
        unmatched_loads = export_unmatched_loads(self.grid)
        assert unmatched_loads["unmatched_load_count"] == 20
        assert not unmatched_loads["all_loads_met"]

    def test_export_unmatched_loads_is_reported_correctly_for_half_loads_unmatched(self):
        house1 = Area("House1", [self.area1, self.area2])
        for i in range(1, 11):
            timeslot = Pendulum(2018, 1, 1, 12+i, 0, 0)
            mock_market = MagicMock(spec=Market)
            mock_market.traded_energy = {"load1":  90}
            self.strategy1.state.desired_energy[timeslot] = 100
            self.area1.past_markets[timeslot] = mock_market

            mock_market = MagicMock(spec=Market)
            mock_market.traded_energy = {"load2": 101}
            self.strategy2.energy = 100
            self.area2.past_markets[timeslot] = mock_market

            mock_market3 = MagicMock(spec=Market)
            mock_market3.traded_energy = {"load1":  100, "load2": 101}
            house1.past_markets[timeslot] = mock_market3
        self.grid = Area("Grid", [house1])
        unmatched_loads = export_unmatched_loads(self.grid)
        assert unmatched_loads["unmatched_load_count"] == 10
        assert not unmatched_loads["all_loads_met"]

    def test_export_unmatched_loads_reports_cell_tower_areas(self):
        house1 = Area("House1", [self.area1, self.area2])
        ct_strategy = MagicMock(spec=CellTowerLoadHoursStrategy)
        ct_strategy.state = MagicMock(spec=LoadState)
        ct_strategy.state.desired_energy = {}
        cell_tower = Area("Cell Tower", strategy=ct_strategy)
        for i in range(1, 11):
            timeslot = Pendulum(2018, 1, 1, 12+i, 0, 0)
            mock_market = MagicMock(spec=Market)
            mock_market.traded_energy = {"load1":  90}
            self.strategy1.state.desired_energy[timeslot] = 100
            self.area1.past_markets[timeslot] = mock_market

            mock_market = MagicMock(spec=Market)
            mock_market.traded_energy = {"load2": 99}
            self.strategy2.energy = 100
            self.area2.past_markets[timeslot] = mock_market

            mock_market3 = MagicMock(spec=Market)
            mock_market3.traded_energy = {"load1":  100, "load2": 101}
            house1.past_markets[timeslot] = mock_market3

            mock_market_ct = MagicMock(spec=Market)
            mock_market_ct.traded_energy = {"Cell Tower": 400}
            ct_strategy.state.desired_energy[timeslot] = 1000
            cell_tower.past_markets[timeslot] = mock_market_ct

        self.grid = Area("Grid", [house1, cell_tower])
        unmatched_loads = export_unmatched_loads(self.grid)
        assert unmatched_loads["unmatched_load_count"] == 30
        assert not unmatched_loads["all_loads_met"]
