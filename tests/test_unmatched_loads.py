"""
Copyright 2018 Grid Singularity
This file is part of D3A.

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
from pendulum import duration, today
from d3a.d3a_core.sim_results.export_unmatched_loads import ExportUnmatchedLoads
from unittest.mock import MagicMock
import unittest
from d3a.models.area import Area
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.load_hours import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.state import LoadState
from d3a.models.config import SimulationConfig
from d3a.models.market import Market
from d3a.constants import DATE_TIME_FORMAT, TIME_ZONE
from d3a.d3a_core.sim_results.export_unmatched_loads import get_number_of_unmatched_loads


class TestUnmatchedLoad(unittest.TestCase):

    def setUp(self):
        self.appliance = MagicMock(spec=SimpleAppliance)

        self.strategy1 = MagicMock(spec=LoadHoursStrategy)
        self.strategy1.state = MagicMock(spec=LoadState)
        self.strategy1.state.desired_energy_Wh = {}
        self.strategy2 = MagicMock(spec=LoadHoursStrategy)
        self.strategy2.state = MagicMock(spec=LoadState)
        self.strategy2.state.desired_energy_Wh = {}
        self.strategy3 = MagicMock(spec=DefinedLoadStrategy)
        self.strategy3.state = MagicMock(spec=LoadState)
        self.strategy3.state.desired_energy_Wh = {}
        self.config = MagicMock(spec=SimulationConfig)
        self.config.slot_length = duration(minutes=15)
        self.config.tick_length = duration(seconds=15)
        self.config.start_date = today(tz=TIME_ZONE)
        self.area1 = Area("load1", None, None, self.strategy1, self.appliance,
                          self.config, None, transfer_fee_pct=0)
        self.area2 = Area("load2", None, None, self.strategy2, self.appliance,
                          self.config, None, transfer_fee_pct=0)
        self.area3 = Area("load3", None, None, self.strategy3, self.appliance,
                          self.config, None, transfer_fee_pct=0)

    def tearDown(self):
        pass

    def test_export_unmatched_loads_is_reported_correctly_for_all_loads_matched(self):
        house1 = Area("House1", [self.area1, self.area2])
        self.grid = Area("Grid", [house1])
        self.grid._markets.past_markets = {}
        for i in range(1, 11):
            timeslot = today(tz=TIME_ZONE).add(hours=12+i)
            self.strategy1.state.desired_energy_Wh[timeslot] = 100
            self.strategy2.state.desired_energy_Wh[timeslot] = 100
            mock_market = MagicMock(spec=Market)
            mock_market.time_slot = timeslot
            mock_market.traded_energy = {"load1": -0.101, "load2": -0.101}
            house1._markets.past_markets[timeslot] = mock_market
            self.grid._markets.past_markets[timeslot] = mock_market

        unmatched_loads, unmatched_loads_redis = ExportUnmatchedLoads(self.grid)()

        assert list(unmatched_loads[self.grid.name].keys()) == ['House1']
        assert get_number_of_unmatched_loads(unmatched_loads) == 0

    def test_export_unmatched_loads_is_reported_correctly_for_all_loads_unmatched(self):
        house1 = Area("House1", [self.area1, self.area2])
        self.grid = Area("Grid", [house1])
        self.grid._markets.past_markets = {}
        for i in range(1, 11):
            timeslot = today(tz=TIME_ZONE).add(hours=12+i)
            self.strategy1.state.desired_energy_Wh[timeslot] = 100
            self.strategy2.state.desired_energy_Wh[timeslot] = 100
            mock_market = MagicMock(spec=Market)
            mock_market.time_slot = timeslot
            mock_market.time_slot_str = timeslot.format(DATE_TIME_FORMAT)
            mock_market.traded_energy = {"load1": -0.09, "load2": -0.07}
            house1._markets.past_markets[timeslot] = mock_market
            self.grid._markets.past_markets[timeslot] = mock_market
        unmatched_loads, unmatched_loads_redis = ExportUnmatchedLoads(self.grid)()
        assert get_number_of_unmatched_loads(unmatched_loads) == 20

    def test_export_unmatched_loads_is_reported_correctly_for_half_loads_unmatched(self):
        house1 = Area("House1", [self.area1, self.area2])
        self.grid = Area("Grid", [house1])
        self.grid._markets.past_markets = {}
        for i in range(1, 11):
            timeslot = today(tz=TIME_ZONE).add(hours=12+i)
            self.strategy1.state.desired_energy_Wh[timeslot] = 100
            self.strategy2.state.desired_energy_Wh[timeslot] = 100
            mock_market = MagicMock(spec=Market)
            mock_market.time_slot = timeslot
            mock_market.traded_energy = {"load1": -0.09, "load2": -0.101}
            house1._markets.past_markets[timeslot] = mock_market
            self.grid._markets.past_markets[timeslot] = mock_market

        unmatched_loads, unmatched_loads_redis = ExportUnmatchedLoads(self.grid)()
        assert get_number_of_unmatched_loads(unmatched_loads) == 10

    def test_export_unmatched_loads_reports_cell_tower_areas(self):
        house1 = Area("House1", [self.area1, self.area2])
        ct_strategy = MagicMock(spec=CellTowerLoadHoursStrategy)
        ct_strategy.state = MagicMock(spec=LoadState)
        ct_strategy.state.desired_energy_Wh = {}
        cell_tower = Area("Cell Tower", strategy=ct_strategy)
        self.grid = Area("Grid", [house1, cell_tower])
        for i in range(1, 11):
            timeslot = today(tz=TIME_ZONE).add(hours=12+i)
            self.strategy1.state.desired_energy_Wh[timeslot] = 100
            self.strategy2.state.desired_energy_Wh[timeslot] = 100

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

        unmatched_loads, unmatched_loads_redis = ExportUnmatchedLoads(self.grid)()
        assert get_number_of_unmatched_loads(unmatched_loads) == 30

    def test_export_unmatched_loads_is_reported_correctly_for_predefined_load_strategy(self):
        house1 = Area("House1", [self.area1, self.area3])
        self.grid = Area("Grid", [house1])
        self.grid._markets.past_markets = {}
        for i in range(1, 11):
            timeslot = today(tz=TIME_ZONE).add(hours=12+i)
            mock_market = MagicMock(spec=Market)
            mock_market.time_slot = timeslot
            self.strategy1.state.desired_energy_Wh[timeslot] = 100
            self.strategy3.state.desired_energy_Wh[timeslot] = 80
            mock_market.traded_energy = {"load1": -0.099, "load3": -0.079}
            house1._markets.past_markets[timeslot] = mock_market
            self.grid._markets.past_markets[timeslot] = mock_market
        unmatched_loads, unmatched_loads_redis = ExportUnmatchedLoads(self.grid)()
        assert get_number_of_unmatched_loads(unmatched_loads) == 20

    def test_export_unmatched_loads_is_reporting_correctly_the_device_types(self):
        self.area1.display_type = "Area 1 type"
        self.area3.display_type = "Area 3 type"
        house1 = Area("House1", [self.area1, self.area3])
        self.grid = Area("Grid", [house1])
        unmatched_loads, unmatched_loads_redis = ExportUnmatchedLoads(self.grid)()
        assert get_number_of_unmatched_loads(unmatched_loads) == 0
        assert "type" not in unmatched_loads["House1"]
        assert unmatched_loads["House1"]["load1"]["type"] == "Area 1 type"
        assert unmatched_loads["House1"]["load3"]["type"] == "Area 3 type"
        assert unmatched_loads_redis[house1.uuid]["load1"]["type"] == "Area 1 type"
        assert unmatched_loads_redis[house1.uuid]["load3"]["type"] == "Area 3 type"
        assert "type" not in unmatched_loads["Grid"]
        assert unmatched_loads["Grid"]["House1"]["type"] == "Area"
        assert unmatched_loads_redis[self.grid.uuid]["House1"]["type"] == "Area"
