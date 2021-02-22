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
from copy import deepcopy
from unittest.mock import MagicMock
import unittest
from d3a.models.area import Area

from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.state import LoadState
from d3a.models.config import SimulationConfig
from d3a.models.market import Market
from d3a.constants import DATE_TIME_FORMAT, TIME_ZONE
from d3a_interface.sim_results.export_unmatched_loads import get_number_of_unmatched_loads
from d3a.d3a_core.sim_results.endpoint_buffer import SimulationEndpointBuffer
from d3a.models.market.market_structures import Trade, Bid


class TestUnmatchedLoad(unittest.TestCase):

    def setUp(self):
        self.config = MagicMock(spec=SimulationConfig)
        self.config.slot_length = duration(minutes=15)
        self.config.tick_length = duration(seconds=15)
        self.config.start_date = today(tz=TIME_ZONE)
        self.config.grid_fee_type = 1

        self.strategy1 = MagicMock(spec=LoadHoursStrategy)
        self.strategy1.state = LoadState()
        self.strategy2 = MagicMock(spec=LoadHoursStrategy)
        self.strategy2.state = LoadState()
        self.strategy3 = MagicMock(spec=DefinedLoadStrategy)
        self.strategy3.state = LoadState()
        self.area1 = Area("load1", None, None, self.strategy1,
                          self.config, None, grid_fee_percentage=0)
        self.area2 = Area("load2", None, None, self.strategy2,
                          self.config, None, grid_fee_percentage=0)
        self.area3 = Area("load3", None, None, self.strategy3,
                          self.config, None, grid_fee_percentage=0)

    def tearDown(self):
        pass

    def test_export_unmatched_loads_is_reported_correctly_for_all_loads_matched(self):
        house1 = Area("House1", [self.area1, self.area2])
        self.grid = Area("Grid", [house1])
        self.grid._markets.past_markets = {}
        epb = SimulationEndpointBuffer("1", {"seed": 0}, self.grid, True)

        for i in range(1, 11):
            timeslot = today(tz=TIME_ZONE).add(hours=12+i)
            self.strategy1.state._desired_energy_Wh[timeslot] = 100
            self.strategy2.state._desired_energy_Wh[timeslot] = 100
            mock_market = MagicMock(spec=Market)
            mock_market.time_slot = timeslot
            mock_market.time_slot_str = timeslot.format(DATE_TIME_FORMAT)
            mock_market.const_fee_rate = None

            self.area1._markets.past_markets[timeslot] = deepcopy(mock_market)
            self.area1._markets.past_markets[timeslot].trades = [
                Trade("123", timeslot,
                      Bid("23", timeslot, 1, 1.01, 'load1', 1, 'load1'),
                      'abc', 'load1', seller_origin='abc', buyer_origin='load1')
            ]
            self.area2._markets.past_markets[timeslot] = deepcopy(mock_market)
            self.area2._markets.past_markets[timeslot].trades = [
                Trade("123", timeslot,
                      Bid("23", timeslot, 1, 1.01, 'load2', 1, 'load2'),
                      'abc', 'load2', seller_origin='abc', buyer_origin='load2')
            ]

            epb.current_market_time_slot_str = mock_market.time_slot_str
            epb._create_area_tree_dict(self.grid)
            epb._populate_core_stats_and_sim_state(self.grid)

            house1._markets.past_markets[timeslot] = mock_market
            self.grid._markets.past_markets[timeslot] = mock_market

            epb.results_handler.update(
                epb.area_result_dict, epb.flattened_area_core_stats_dict,
                current_market_slot=mock_market.time_slot)
            unmatched_loads = epb.results_handler.results_mapping["unmatched_loads"].raw_results

            assert list(unmatched_loads['Grid'].keys()) == ['House1']
            assert get_number_of_unmatched_loads(unmatched_loads) == 0

    def test_export_unmatched_loads_is_reported_correctly_for_all_loads_unmatched(self):
        house1 = Area("House1", [self.area1, self.area2])
        self.grid = Area("Grid", [house1])
        self.grid._markets.past_markets = {}
        epb = SimulationEndpointBuffer("1", {"seed": 0}, self.grid, True)
        cumulative_unmatched_load = 0

        for i in range(1, 11):
            timeslot = today(tz=TIME_ZONE).add(hours=12+i)
            self.strategy1.state._desired_energy_Wh[timeslot] = 100
            self.strategy2.state._desired_energy_Wh[timeslot] = 100
            mock_market = MagicMock(spec=Market)
            mock_market.time_slot = timeslot
            mock_market.time_slot_str = timeslot.format(DATE_TIME_FORMAT)
            self.area1._markets.past_markets[timeslot] = deepcopy(mock_market)
            self.area1._markets.past_markets[timeslot].trades = [
                Trade("123", timeslot,
                      Bid("23", timeslot, 1, 0.07, 'load1', 1, 'load1'),
                      'abc', 'load1', seller_origin='abc', buyer_origin='load1')
            ]
            self.area2._markets.past_markets[timeslot] = deepcopy(mock_market)
            self.area2._markets.past_markets[timeslot].trades = [
                Trade("123", timeslot,
                      Bid("23", timeslot, 1, 0.09, 'load2', 1, 'load2'),
                      'abc', 'load2', seller_origin='abc', buyer_origin='load2')
            ]
            epb.current_market_time_slot_str = mock_market.time_slot_str
            epb.current_market_time_slot = mock_market.time_slot
            epb._populate_core_stats_and_sim_state(self.grid)

            epb.results_handler.update(
                epb.area_result_dict, epb.flattened_area_core_stats_dict,
                current_market_slot=mock_market.time_slot_str)

        unmatched_loads = epb.results_handler.results_mapping["unmatched_loads"].raw_results
        cumulative_unmatched_load = get_number_of_unmatched_loads(unmatched_loads)
        assert cumulative_unmatched_load == 20

    def test_export_unmatched_loads_is_reported_correctly_for_half_loads_unmatched(self):
        house1 = Area("House1", [self.area1, self.area2])
        self.grid = Area("Grid", [house1])
        self.grid._markets.past_markets = {}
        epb = SimulationEndpointBuffer("1", {"seed": 0}, self.grid, True)
        cumulative_unmatched_load = 0

        for i in range(1, 11):
            timeslot = today(tz=TIME_ZONE).add(hours=12+i)
            self.strategy1.state._desired_energy_Wh[timeslot] = 100
            self.strategy2.state._desired_energy_Wh[timeslot] = 100
            mock_market = MagicMock(spec=Market)
            mock_market.time_slot = timeslot
            mock_market.time_slot_str = timeslot.format(DATE_TIME_FORMAT)
            mock_market.traded_energy = {"load1": -0.09, "load2": 0.101}
            self.area1._markets.past_markets[timeslot] = deepcopy(mock_market)
            self.area1._markets.past_markets[timeslot].trades = [
                Trade("123", timeslot,
                      Bid("23", timeslot, 1, 0.05, 'load1', 1, 'load1'),
                      'abc', 'load1', seller_origin='abc', buyer_origin='load1')
            ]
            self.area2._markets.past_markets[timeslot] = deepcopy(mock_market)
            self.area2._markets.past_markets[timeslot].trades = [
                Trade("123", timeslot,
                      Bid("23", timeslot, 1, 1.05, 'load2', 1, 'load2'),
                      'abc', 'load2', seller_origin='abc', buyer_origin='load2')
            ]
            epb.current_market_time_slot_str = mock_market.time_slot_str
            epb.current_market_time_slot = mock_market.time_slot
            epb._populate_core_stats_and_sim_state(self.grid)
            epb.results_handler.update(
                epb.area_result_dict, epb.flattened_area_core_stats_dict,
                current_market_slot=mock_market.time_slot_str)

        unmatched_loads = epb.results_handler.results_mapping["unmatched_loads"].raw_results
        cumulative_unmatched_load = get_number_of_unmatched_loads(unmatched_loads)
        assert cumulative_unmatched_load == 10

    def test_export_unmatched_loads_reports_cell_tower_areas(self):
        house1 = Area("House1", [self.area1, self.area2])
        ct_strategy = MagicMock(spec=LoadHoursStrategy)
        ct_strategy.state = LoadState()
        cell_tower = Area("Cell Tower", strategy=ct_strategy)
        self.grid = Area("Grid", [house1, cell_tower])
        epb = SimulationEndpointBuffer("1", {"seed": 0}, self.grid, True)
        cumulative_unmatched_load = 0

        for i in range(1, 11):
            timeslot = today(tz=TIME_ZONE).add(hours=12+i)
            self.strategy1.state._desired_energy_Wh[timeslot] = 100
            self.strategy2.state._desired_energy_Wh[timeslot] = 100

            mock_market = MagicMock(spec=Market)
            mock_market.time_slot = timeslot
            mock_market.time_slot_str = timeslot.format(DATE_TIME_FORMAT)
            mock_market.const_fee_rate = None
            self.area1._markets.past_markets[timeslot] = deepcopy(mock_market)
            self.area1._markets.past_markets[timeslot].trades = [
                Trade("123", timeslot,
                      Bid("23", timeslot, 1, 0.05, 'load1', 1, 'load1'),
                      'abc', 'load1', seller_origin='abc', buyer_origin='load1')
            ]
            self.area2._markets.past_markets[timeslot] = deepcopy(mock_market)
            self.area2._markets.past_markets[timeslot].trades = [
                Trade("123", timeslot,
                      Bid("23", timeslot, 1, 0.06, 'load2', 1, 'load2'),
                      'abc', 'load2', seller_origin='abc', buyer_origin='load2')
            ]

            ct_strategy.state._desired_energy_Wh[timeslot] = 1000
            cell_tower._markets.past_markets[timeslot] = deepcopy(mock_market)
            cell_tower._markets.past_markets[timeslot].trades = [
                Trade("123", timeslot,
                      Bid("24", timeslot, 1, 0.05, 'Cell Tower', 1, 'Cell Tower'),
                      'abc', 'Cell Tower', seller_origin='abc', buyer_origin='Cell Tower')
            ]
            self.grid._markets.past_markets[timeslot] = deepcopy(mock_market)
            epb.current_market_time_slot_str = mock_market.time_slot_str
            epb.current_market_time_slot = mock_market.time_slot
            epb._populate_core_stats_and_sim_state(self.grid)

            epb.results_handler.update(
                epb.area_result_dict, epb.flattened_area_core_stats_dict,
                current_market_slot=mock_market.time_slot_str)

        unmatched_loads = epb.results_handler.results_mapping["unmatched_loads"].raw_results
        cumulative_unmatched_load = get_number_of_unmatched_loads(unmatched_loads)
        assert cumulative_unmatched_load == 30

    def test_export_unmatched_loads_is_reported_correctly_for_predefined_load_strategy(self):
        house1 = Area("House1", [self.area1, self.area3])
        self.grid = Area("Grid", [house1])
        self.grid._markets.past_markets = {}
        epb = SimulationEndpointBuffer("1", {"seed": 0}, self.grid, True)
        cumulative_unmatched_load = 0
        for i in range(1, 11):
            timeslot = today(tz=TIME_ZONE).add(hours=12+i)
            mock_market = MagicMock(spec=Market)
            mock_market.time_slot = timeslot
            mock_market.time_slot_str = timeslot.format(DATE_TIME_FORMAT)
            self.strategy1.state._desired_energy_Wh[timeslot] = 100
            self.strategy3.state._desired_energy_Wh[timeslot] = 80
            self.area1._markets.past_markets[timeslot] = deepcopy(mock_market)
            self.area1._markets.past_markets[timeslot].trades = [
                Trade("123", timeslot,
                      Bid("23", timeslot, 1, 0.099, 'load1', 1, 'load1'),
                      'abc', 'load1', seller_origin='abc', buyer_origin='load1')
            ]
            self.area3._markets.past_markets[timeslot] = deepcopy(mock_market)
            self.area3._markets.past_markets[timeslot].trades = [
                Trade("123", timeslot,
                      Bid("23", timeslot, 1, 0.079, 'load3', 1, 'load3'),
                      'abc', 'load3', seller_origin='abc', buyer_origin='load3')
            ]
            epb.current_market_time_slot_str = mock_market.time_slot_str
            epb.current_market_time_slot = mock_market.time_slot
            epb._populate_core_stats_and_sim_state(self.grid)

            epb.results_handler.update(
                epb.area_result_dict, epb.flattened_area_core_stats_dict,
                current_market_slot=mock_market.time_slot_str)

        unmatched_loads = epb.results_handler.results_mapping["unmatched_loads"].raw_results
        cumulative_unmatched_load = get_number_of_unmatched_loads(unmatched_loads)
        assert cumulative_unmatched_load == 20

    def test_export_unmatched_loads_is_reporting_correctly_the_device_types(self):
        self.area1.display_type = "Area 1 type"
        self.area3.display_type = "Area 3 type"
        house1 = Area("House1", [self.area1, self.area3])
        self.grid = Area("Grid", [house1])
        epb = SimulationEndpointBuffer("1", {"seed": 0}, self.grid, True)

        timeslot = today(tz=TIME_ZONE).add(hours=1)

        mock_market = MagicMock(spec=Market)
        mock_market.time_slot = timeslot
        mock_market.time_slot_str = timeslot.format(DATE_TIME_FORMAT)
        epb.current_market_time_slot_str = mock_market.time_slot_str
        self.area1._markets.past_markets[timeslot] = deepcopy(mock_market)
        self.area3._markets.past_markets[timeslot] = deepcopy(mock_market)

        epb._populate_core_stats_and_sim_state(self.grid)

        epb.results_handler.update(
            epb.area_result_dict, epb.flattened_area_core_stats_dict,
            current_market_slot=mock_market.time_slot_str)
        unmatched_loads = epb.results_handler.results_mapping["unmatched_loads"].raw_results
        unmatched_loads_redis = \
            epb.results_handler.results_mapping["unmatched_loads"].ui_formatted_results

        assert get_number_of_unmatched_loads(unmatched_loads) == 0
        assert "type" not in unmatched_loads["House1"]
        assert unmatched_loads["House1"]["load1"]["type"] == "LoadHoursStrategy"
        assert unmatched_loads["House1"]["load3"]["type"] == "DefinedLoadStrategy"
        assert unmatched_loads_redis[house1.uuid]["load1"]["type"] == "LoadHoursStrategy"
        assert unmatched_loads_redis[house1.uuid]["load3"]["type"] == "DefinedLoadStrategy"
        assert "type" not in unmatched_loads["Grid"]
        assert unmatched_loads["Grid"]["House1"]["type"] == "Area"
        assert unmatched_loads_redis[self.grid.uuid]["House1"]["type"] == "Area"

    def test_export_none_if_no_loads_in_setup(self):
        house1 = Area("House1", [])
        self.grid = Area("Grid", [house1])
        epb = SimulationEndpointBuffer("1", {"seed": 0}, self.grid, True)
        timeslot = today(tz=TIME_ZONE).add(hours=1)

        mock_market = MagicMock(spec=Market)
        mock_market.time_slot = timeslot
        mock_market.time_slot_str = timeslot.format(DATE_TIME_FORMAT)
        mock_market.const_fee_rate = None
        epb.current_market_time_slot_str = mock_market.time_slot_str
        self.grid._markets.past_markets[timeslot] = deepcopy(mock_market)
        self.area1._markets.past_markets[timeslot] = deepcopy(mock_market)
        self.area3._markets.past_markets[timeslot] = deepcopy(mock_market)
        epb._populate_core_stats_and_sim_state(self.grid)
        epb.results_handler.update(
            epb.area_result_dict, epb.flattened_area_core_stats_dict,
            current_market_slot=self.config.start_date)
        unmatched_loads = epb.results_handler.results_mapping["unmatched_loads"].raw_results
        assert unmatched_loads["House1"] is None
        assert unmatched_loads["Grid"] is None

    def test_export_something_if_loads_in_setup(self):
        house1 = Area("House1", [self.area1, self.area3])
        self.grid = Area("Grid", [house1])
        epb = SimulationEndpointBuffer("1", {"seed": 0}, self.grid, True)

        timeslot = today(tz=TIME_ZONE).add(hours=1)

        mock_market = MagicMock(spec=Market)
        mock_market.time_slot = timeslot
        mock_market.time_slot_str = timeslot.format(DATE_TIME_FORMAT)
        mock_market.const_fee_rate = None
        epb.current_market_time_slot_str = mock_market.time_slot_str
        self.grid._markets.past_markets[timeslot] = deepcopy(mock_market)
        epb._populate_core_stats_and_sim_state(self.grid)
        epb.results_handler.update(
            epb.area_result_dict, epb.flattened_area_core_stats_dict,
            current_market_slot=self.config.start_date)
        unmatched_loads = epb.results_handler.results_mapping["unmatched_loads"].raw_results
        assert unmatched_loads["House1"] is not None
        assert unmatched_loads["Grid"] is not None
