"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
from unittest.mock import MagicMock

from pendulum import duration, today
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import SpotMarketTypeEnum

from gsy_e.constants import TIME_ZONE
from gsy_e.gsy_e_core.global_stats import ExternalConnectionGlobalStatistics
from gsy_e.gsy_e_core.redis_connections.area_market import ExternalConnectionCommunicator
from gsy_e.models.area import Area
from gsy_e.models.config import SimulationConfig
from gsy_e.models.strategy.external_strategies.load import LoadHoursExternalStrategy
from gsy_e.models.strategy.external_strategies.pv import PVExternalStrategy
from gsy_e.models.strategy.external_strategies.storage import StorageExternalStrategy


class TestGlobalObjects:

    def setup_method(self):
        # pylint: disable=attribute-defined-outside-init
        ConstSettings.MASettings.MARKET_TYPE = SpotMarketTypeEnum.ONE_SIDED.value
        self.config = MagicMock(spec=SimulationConfig)
        self.config.slot_length = duration(minutes=15)
        self.config.tick_length = duration(seconds=15)
        self.config.ticks_per_slot = int(self.config.slot_length.seconds /
                                         self.config.tick_length.seconds)
        self.config.start_date = today(tz=TIME_ZONE)
        self.config.sim_duration = duration(days=1)
        self.config.grid_fee_type = 1
        self.config.end_date = self.config.start_date + self.config.sim_duration
        self.config.capacity_kW = 1
        self.config.external_redis_communicator = \
            MagicMock(spec=ExternalConnectionCommunicator(True))
        self.storage = Area("Storage", strategy=StorageExternalStrategy(), config=self.config,
                            external_connection_available=True)
        self.load = Area("Load", strategy=LoadHoursExternalStrategy(avg_power_W=100),
                         config=self.config, external_connection_available=True)
        self.pv = Area("PV", strategy=PVExternalStrategy(), config=self.config,
                       external_connection_available=True)
        self.house_area = Area("House", children=[self.storage, self.load, self.pv],
                               config=self.config)
        self.grid_area = Area("Grid", children=[self.house_area], config=self.config)
        self.grid_area.activate()

    def test_global_objects_area_stats_tree_dict_general_structure(self):
        go = ExternalConnectionGlobalStatistics()
        go(self.grid_area, self.config.ticks_per_slot)
        self.grid_area.current_tick += 15
        self.house_area.current_tick += 15
        self.grid_area.cycle_markets(_trigger_event=True)

        go.update()

        expected_area_stats_tree_dict = {
            self.grid_area.uuid:
                {"last_market_bill": {"accumulated_trades": {}, "external_trades": {}},
                 "last_market_stats": {"min_trade_rate": None, "max_trade_rate": None,
                                       "avg_trade_rate": None, "median_trade_rate": None,
                                       "total_traded_energy_kWh": None},
                 "last_market_fee": 0.0,
                 "current_market_fee": None,
                 "area_name": "Grid",
                 "children": {
                     self.house_area.uuid: {
                         "last_market_bill": {"accumulated_trades": {},
                                              "external_trades": {}},
                         "last_market_stats": {"min_trade_rate": None,
                                               "max_trade_rate": None,
                                               "avg_trade_rate": None,
                                               "median_trade_rate": None,
                                               "total_traded_energy_kWh": None},
                         "last_market_fee": 0.0,
                         "current_market_fee": None,
                         "area_name": "House",
                         "children": {
                             self.storage.uuid: {
                                  "asset_info": {"energy_to_sell": 0.0,
                                                 "energy_active_in_bids": 0,
                                                 "energy_to_buy": 1.08,
                                                 "energy_active_in_offers": 0,
                                                 "free_storage": 1.08,
                                                 "used_storage": 0.12,
                                                 "energy_traded": 0.0,
                                                 "total_cost": 0.0},
                                  "last_slot_asset_info": {"energy_traded": 0.0,
                                                           "total_cost": 0.0},
                                  "asset_bill": None,
                                  "area_name": "Storage"},
                             self.load.uuid: {"asset_info": {
                                        "energy_requirement_kWh": 0.025,
                                        "energy_active_in_bids": 0.0,
                                        "energy_traded": 0.0,
                                        "total_cost": 0.0},
                                    "last_slot_asset_info": {
                                        "energy_traded": 0.0,
                                        "total_cost": 0.0},
                                    "asset_bill": None,
                                    "area_name": "Load"},
                             self.pv.uuid: {"asset_info": {
                                      "available_energy_kWh": 0.0,
                                      "energy_active_in_offers": 0,
                                      "energy_traded": 0,
                                      "total_cost": 0},
                                  "last_slot_asset_info": {
                                         "energy_traded": 0,
                                         "total_cost": 0},
                                  "asset_bill": None,
                                  "area_name": "PV"
                                  }}}}}}

        assert expected_area_stats_tree_dict == go.area_stats_tree_dict
