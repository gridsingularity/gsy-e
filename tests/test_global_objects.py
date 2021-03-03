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
from unittest.mock import MagicMock
import unittest
from d3a.models.area import Area
from d3a.models.strategy.external_strategies.storage import StorageExternalStrategy
from d3a.models.strategy.external_strategies.load import LoadHoursExternalStrategy
from d3a.models.strategy.external_strategies.pv import PVExternalStrategy
from d3a.d3a_core.global_objects import GlobalObjects
from d3a.models.config import SimulationConfig
from d3a.constants import TIME_ZONE
from d3a.d3a_core.redis_connections.redis_area_market_communicator import \
    ExternalConnectionCommunicator


class TestGlobalObjects(unittest.TestCase):

    def setUp(self):
        self.config = MagicMock(spec=SimulationConfig)
        self.config.slot_length = duration(minutes=15)
        self.config.tick_length = duration(seconds=15)
        self.config.ticks_per_slot = int(self.config.slot_length.seconds /
                                         self.config.tick_length.seconds)
        self.config.start_date = today(tz=TIME_ZONE)
        self.config.sim_duration = duration(days=1)
        self.config.grid_fee_type = 1
        self.config.end_date = self.config.start_date + self.config.sim_duration
        self.config.market_count = 1
        self.config.max_panel_power_W = 1000
        self.config.external_redis_communicator = \
            MagicMock(spec=ExternalConnectionCommunicator(True))
        self.storage = Area("Storage", strategy=StorageExternalStrategy(), config=self.config)
        self.load = Area("Load", strategy=LoadHoursExternalStrategy(avg_power_W=100),
                         config=self.config)
        self.pv = Area("PV", strategy=PVExternalStrategy(), config=self.config)
        self.house_area = Area("House", children=[self.storage, self.load, self.pv],
                               config=self.config)
        self.grid_area = Area("Grid", children=[self.house_area], config=self.config)
        self.grid_area.activate()

    def test_global_objects_area_stats_tree_dict_general_structure(self):
        go = GlobalObjects()
        self.grid_area.current_tick += 15
        self.house_area.current_tick += 15
        self.grid_area.cycle_markets(_trigger_event=True)

        go.update(self.grid_area)

        expected_area_stats_tree_dict = {
            'Grid': {'market_maker_rate': 30,
                     'last_market_bill': {'accumulated_trades': {}, 'external_trades': {}},
                     'last_market_stats': {'min_trade_rate': None, 'max_trade_rate': None,
                                           'avg_trade_rate': None, 'median_trade_rate': None,
                                           'total_traded_energy_kWh': None},
                     'last_market_fee': 0.0,
                     'current_market_fee': None,
                     'area_uuid': self.grid_area.uuid,
                     'children': {
                         'House': {'market_maker_rate': 30,
                                   'last_market_bill': {'accumulated_trades': {},
                                                        'external_trades': {}},
                                   'last_market_stats': {'min_trade_rate': None,
                                                         'max_trade_rate': None,
                                                         'avg_trade_rate': None,
                                                         'median_trade_rate': None,
                                                         'total_traded_energy_kWh': None},
                                   'last_market_fee': 0.0,
                                   'current_market_fee': None,
                                   'area_uuid': self.house_area.uuid,
                                   'children': {
                                       'Storage': {
                                          'asset_info': {'energy_to_sell': 0.0,
                                                         'energy_active_in_bids': 0,
                                                         'energy_to_buy': 1.08,
                                                         'energy_active_in_offers': 0,
                                                         'free_storage': 1.08,
                                                         'used_storage': 0.12,
                                                         'energy_traded': 0.0,
                                                         'total_cost': 0.0},
                                          'last_slot_asset_info': {'energy_traded': 0.0,
                                                                   'total_cost': 0.0},
                                          'device_bill': None,
                                          'area_uuid': self.storage.uuid},
                                       'Load': {'asset_info': {
                                                    'energy_requirement_kWh': 0.025,
                                                    'energy_active_in_bids': 0.0,
                                                    'energy_traded': 0.0,
                                                    'total_cost': 0.0},
                                                'last_slot_asset_info': {
                                                    'energy_traded': 0.0,
                                                    'total_cost': 0.0},
                                                'device_bill': None,
                                                'area_uuid': self.load.uuid},
                                       'PV': {'asset_info': {
                                                  'available_energy_kWh': 0.0,
                                                  'energy_active_in_offers': 0,
                                                  'energy_traded': 0,
                                                  'total_cost': 0},
                                              'last_slot_asset_info': {
                                                     'energy_traded': 0,
                                                     'total_cost': 0},
                                              'device_bill': None,
                                              'area_uuid': self.pv.uuid
                                              }}}}}}

        assert expected_area_stats_tree_dict == go.area_stats_tree_dict
