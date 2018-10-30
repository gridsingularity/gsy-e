from pendulum import duration, DateTime
from d3a.export_unmatched_loads import export_unmatched_loads
from unittest.mock import MagicMock
import unittest
from d3a.models.area import Area
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.state import LoadState
from d3a.models.strategy.permanent import PermanentLoadStrategy
from d3a.models.config import SimulationConfig
from d3a.models.market import Market


class TestUnmatchedLoad(unittest.TestCase):

    def setUp(self):
        self.appliance = MagicMock(spec=SimpleAppliance)
        self.strategy1 = MagicMock(spec=LoadHoursStrategy)
        self.strategy1.state = MagicMock(spec=LoadState)
        self.strategy1.state.desired_energy_Wh = {}
        self.strategy2 = MagicMock(spec=PermanentLoadStrategy)
        self.strategy3 = MagicMock(spec=DefinedLoadStrategy)
        self.strategy3.state = MagicMock(spec=LoadState)
        self.strategy3.state.desired_energy_Wh = {}
        self.config = MagicMock(spec=SimulationConfig)
        self.config.slot_length = duration(minutes=15)
        self.config.tick_length = duration(seconds=15)
        self.area1 = Area("load1", None, self.strategy1, self.appliance, self.config, None)
        self.area2 = Area("load2", None, self.strategy2, self.appliance, self.config, None)
        self.area3 = Area("load3", None, self.strategy3, self.appliance, self.config, None)

    def tearDown(self):
        pass

    def test_export_unmatched_loads_is_reported_correctly_for_all_loads_matched(self):
        house1 = Area("House1", [self.area1, self.area2])
        self.grid = Area("Grid", [house1])
        self.grid._markets.past_markets = {}
        for i in range(1, 11):
            timeslot = DateTime(2018, 1, 1, 12+i, 0, 0)
            self.strategy1.state.desired_energy_Wh[timeslot] = 100
            self.strategy2.energy = 100
            mock_market = MagicMock(spec=Market)
            mock_market.time_slot = timeslot
            mock_market.traded_energy = {"load1": -0.101, "load2": -0.101}
            house1._markets.past_markets[timeslot] = mock_market
            self.grid._markets.past_markets[timeslot] = mock_market

        unmatched_loads = export_unmatched_loads(self.grid)
        assert unmatched_loads["unmatched_load_count"] == 0
        assert unmatched_loads["all_loads_met"]

    def test_export_unmatched_loads_is_reported_correctly_for_all_loads_unmatched(self):
        house1 = Area("House1", [self.area1, self.area2])
        self.grid = Area("Grid", [house1])
        self.grid._markets.past_markets = {}
        for i in range(1, 11):
            timeslot = DateTime(2018, 1, 1, 12+i, 0, 0)
            self.strategy1.state.desired_energy_Wh[timeslot] = 100
            self.strategy2.energy = 100
            mock_market = MagicMock(spec=Market)
            mock_market.time_slot = timeslot
            mock_market.traded_energy = {"load1": -0.09, "load2": -0.07}
            house1._markets.past_markets[timeslot] = mock_market
            self.grid._markets.past_markets[timeslot] = mock_market
        unmatched_loads = export_unmatched_loads(self.grid)
        assert unmatched_loads["unmatched_load_count"] == 20
        assert not unmatched_loads["all_loads_met"]

    def test_export_unmatched_loads_is_reported_correctly_for_half_loads_unmatched(self):
        house1 = Area("House1", [self.area1, self.area2])
        self.grid = Area("Grid", [house1])
        self.grid._markets.past_markets = {}
        for i in range(1, 11):
            timeslot = DateTime(2018, 1, 1, 12+i, 0, 0)
            self.strategy1.state.desired_energy_Wh[timeslot] = 100
            self.strategy2.energy = 100
            mock_market = MagicMock(spec=Market)
            mock_market.time_slot = timeslot
            mock_market.traded_energy = {"load1": -0.09, "load2": -0.101}
            house1._markets.past_markets[timeslot] = mock_market
            self.grid._markets.past_markets[timeslot] = mock_market

        unmatched_loads = export_unmatched_loads(self.grid)
        assert unmatched_loads["unmatched_load_count"] == 10
        assert not unmatched_loads["all_loads_met"]

    def test_export_unmatched_loads_reports_cell_tower_areas(self):
        house1 = Area("House1", [self.area1, self.area2])
        ct_strategy = MagicMock(spec=CellTowerLoadHoursStrategy)
        ct_strategy.state = MagicMock(spec=LoadState)
        ct_strategy.state.desired_energy_Wh = {}
        cell_tower = Area("Cell Tower", strategy=ct_strategy)
        self.grid = Area("Grid", [house1, cell_tower])
        for i in range(1, 11):
            timeslot = DateTime(2018, 1, 1, 12+i, 0, 0)
            self.strategy1.state.desired_energy_Wh[timeslot] = 100
            self.strategy2.energy = 100

            mock_market = MagicMock(spec=Market)
            mock_market.time_slot = timeslot
            mock_market.traded_energy = {"load1": -0.09, "load2": -0.099}
            house1._markets.past_markets[timeslot] = mock_market

            mock_market_ct = MagicMock(spec=Market)
            mock_market_ct.time_slot = timeslot
            mock_market_ct.traded_energy = {"Cell Tower": -0.4}
            ct_strategy.state.desired_energy_Wh[timeslot] = 1000
            cell_tower._markets.past_markets[timeslot] = mock_market_ct

            self.grid._markets.past_markets[timeslot] = mock_market

        unmatched_loads = export_unmatched_loads(self.grid)
        assert unmatched_loads["unmatched_load_count"] == 30
        assert not unmatched_loads["all_loads_met"]

    def test_export_unmatched_loads_is_reported_correctly_for_predefined_load_strategy(self):
        house1 = Area("House1", [self.area1, self.area3])
        self.grid = Area("Grid", [house1])
        self.grid._markets.past_markets = {}
        for i in range(1, 11):
            timeslot = DateTime(2018, 1, 1, 12+i, 0, 0)
            mock_market = MagicMock(spec=Market)
            mock_market.time_slot = timeslot
            self.strategy1.state.desired_energy_Wh[timeslot] = 100
            self.strategy3.state.desired_energy_Wh[timeslot] = 80
            mock_market.traded_energy = {"load1": -0.099, "load3": -0.079}
            house1._markets.past_markets[timeslot] = mock_market
            self.grid._markets.past_markets[timeslot] = mock_market
        unmatched_loads = export_unmatched_loads(self.grid)
        assert unmatched_loads["unmatched_load_count"] == 20
        assert not unmatched_loads["all_loads_met"]
