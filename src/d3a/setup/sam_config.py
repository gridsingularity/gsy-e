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
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.d3a_core.util import d3a_path
import os


def get_setup(config):

    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 PV', strategy=PVStrategy(60, 80),
                         ),
                    Area('H1 Storage1',
                         strategy=StorageStrategy(battery_capacity_kWh=12 * 1.2,
                                                  max_abs_battery_power_kW=12 * 1.2,
                                                  initial_soc=60),
                         ),
                    Area('H1 General Load',
                         strategy=DefinedLoadStrategy(
                             daily_load_profile=os.path.join(d3a_path,
                                                             'resources',
                                                             'SAM_MF2_Summer.csv'),
                             final_buying_rate=35),
                         ),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 PV', strategy=PVStrategy(30, 80),
                         ),
                    Area('H2 Storage1',
                         strategy=StorageStrategy(battery_capacity_kWh=6 * 1.2,
                                                  max_abs_battery_power_kW=6 * 1.2,
                                                  initial_soc=60),
                         ),
                    Area('H2 General Load',
                         strategy=DefinedLoadStrategy(
                             daily_load_profile=os.path.join(d3a_path,
                                                             'resources',
                                                             'SAM_SF_Summer.csv'),
                             final_buying_rate=35),
                         ),

                ]
            ),
            Area(
                'House 3',
                [
                    Area('H3 PV', strategy=PVStrategy(60, 80),
                         ),
                    Area('H3 General Load',
                         strategy=DefinedLoadStrategy(
                             daily_load_profile=os.path.join(d3a_path,
                                                             'resources',
                                                             'SAM_MF2_Summer.csv'),
                             final_buying_rate=35),
                         ),

                ]
            ),
            Area(
                'House 4',
                [
                    Area('H4 PV', strategy=PVStrategy(30, 80),
                         ),
                    Area('H4 General Load',
                         strategy=DefinedLoadStrategy(
                             daily_load_profile=os.path.join(d3a_path,
                                                             'resources',
                                                             'SAM_SF_Summer.csv'),
                             final_buying_rate=35),
                         ),
                ]
            ),
            Area(
                'House 5',
                [
                    Area('H5 Storage1',
                         strategy=StorageStrategy(battery_capacity_kWh=12 * 1.2,
                                                  max_abs_battery_power_kW=12 * 1.2,
                                                  initial_soc=60),
                         ),
                    Area('H5 General Load',
                         strategy=DefinedLoadStrategy(
                             daily_load_profile=os.path.join(d3a_path,
                                                             'resources',
                                                             'SAM_MF2_Summer.csv'),
                             final_buying_rate=35),
                         ),
                ]
            ),
            Area(
                'House 6',
                [
                    Area('H6 Storage1',
                         strategy=StorageStrategy(battery_capacity_kWh=6 * 1.2,
                                                  max_abs_battery_power_kW=6 * 1.2,
                                                  initial_soc=60),
                         ),
                    Area('H6 General Load',
                         strategy=DefinedLoadStrategy(
                             daily_load_profile=os.path.join(d3a_path,
                                                             'resources',
                                                             'SAM_SF_Summer.csv'),
                             final_buying_rate=35),
                         ),

                ]
            ),
            Area(
                'House 7',
                [
                    Area('H7 General Load',
                         strategy=DefinedLoadStrategy(
                             daily_load_profile=os.path.join(d3a_path,
                                                             'resources',
                                                             'SAM_MF2_Summer.csv'),
                             final_buying_rate=35),
                         ),

                ]
            ),
            Area(
                'House 8',
                [
                    Area('H8 General Load',
                         strategy=DefinedLoadStrategy(
                             daily_load_profile=os.path.join(d3a_path,
                                                             'resources',
                                                             'SAM_SF_Summer.csv'),
                             final_buying_rate=35),
                         ),

                ]
            ),
        ],
        config=config
    )
    return area
