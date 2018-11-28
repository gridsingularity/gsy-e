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
# from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
# from d3a.models.strategy.commercial_producer import CommercialStrategy
# from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
# , CellTowerLoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
# from d3a.models.strategy.pv import PVStrategy
# from d3a.models.strategy.predef_load import DefinedLoadStrategy
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy

# import pathlib


def get_setup(config):
    area = Area(
        'Grid',
        [
            # Area(
            #     'House 1',
            #     [
            #         # Area('H1 General Load',
            #         #      strategy=DefinedLoadStrategy(
            #         #          path=pathlib.Path(pathlib.Path.cwd(),
            #         #                     'src/d3a/resources/LOAD_DATA_1.csv').expanduser()),
            #         #      # max_energy_rate=35),
            #         #      appliance=SwitchableAppliance()),
            #         # Area('H1 Storage1', strategy=StorageStrategy(battery_capacity_kWh=1.2,
            #         #                                              initial_charge=40,
            #         #                                              max_abs_battery_power_kW=1.2),
            #         #      appliance=SwitchableAppliance()),
            #
            #     ]
            # ),
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=500,
                                                                       hrs_per_day=18,
                                                                       hrs_of_day=list(
                                                                           range(5, 23))),
                         # max_energy_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H1 PV', strategy=PVPredefinedStrategy(panel_count=1,
                                                                power_profile=1,
                                                                risk=80),
                         appliance=PVAppliance()),
                    # Area('H1 PV', strategy=PVStrategy(2, 80),
                    #      appliance=PVAppliance()),

                ]
            ),
            # Area('Cell Tower', strategy=CellTowerLoadHoursStrategy(avg_power_W=100,
            #                                                hrs_per_day=24,
            #                                               hrs_of_day=list(range(0, 24)),
            #                                             max_energy_rate=35),
            #  appliance=SwitchableAppliance())
            # Area('Commercial Energy Producer',
            #      strategy=CommercialStrategy(energy_range_wh=(40, 120), energy_price=30),
            #      appliance=SimpleAppliance()
            #      ),

        ],
        config=config
    )
    return area
