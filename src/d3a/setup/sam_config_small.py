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
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.d3a_core.util import d3a_path
import os


def get_setup(config):

    i_c = 12 * 1.2
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 PV', strategy=PVStrategy(60, 80),
                         appliance=PVAppliance()),
                    Area('H1 General Load',
                         strategy=DefinedLoadStrategy(
                             daily_load_profile=os.path.join(d3a_path,
                                                             'resources',
                                                             'SAM_MF2_Summer.csv'),
                             final_buying_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(battery_capacity_kWh=i_c,
                                                                 max_abs_battery_power_kW=i_c,
                                                                 initial_soc=100),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 PV', strategy=PVStrategy(60, 80),
                         appliance=PVAppliance()),
                    Area('H2 General Load',
                         strategy=DefinedLoadStrategy(
                             daily_load_profile=os.path.join(d3a_path,
                                                             'resources',
                                                             'SAM_MF2_Summer.csv'),
                             final_buying_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H2 Storage1', strategy=StorageStrategy(battery_capacity_kWh=i_c,
                                                                 max_abs_battery_power_kW=i_c,
                                                                 initial_soc=100),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 3',
                [
                    Area('H3 General Load',
                         strategy=DefinedLoadStrategy(
                             daily_load_profile=os.path.join(d3a_path,
                                                             'resources',
                                                             'SAM_MF2_Summer.csv'),
                             final_buying_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H3 Storage1', strategy=StorageStrategy(battery_capacity_kWh=i_c,
                                                                 max_abs_battery_power_kW=i_c,
                                                                 initial_soc=100),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 4',
                [
                    Area('H4 General Load',
                         strategy=DefinedLoadStrategy(
                             daily_load_profile=os.path.join(d3a_path,
                                                             'resources',
                                                             'SAM_MF2_Summer.csv'),
                             final_buying_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H4 Storage1', strategy=StorageStrategy(battery_capacity_kWh=i_c,
                                                                 max_abs_battery_power_kW=i_c,
                                                                 initial_soc=100),
                         appliance=SwitchableAppliance()),
                ]
            ),
        ],
        config=config
    )
    return area
