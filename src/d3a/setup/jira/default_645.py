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
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.appliance.simple import SimpleAppliance


'''
This setup file is testing the ESS buy functionality. Right now the ESS is not buying even though
the commercial generator price is below the ESS buy threshold'
'''


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [

                    Area('H1 Storage1', strategy=StorageStrategy(
                                                                 initial_capacity_kWh=2,
                                                                 initial_rate_option=2,
                                                                 energy_rate_decrease_option=2,
                                                                 energy_rate_decrease_per_update=3,
                                                                 battery_capacity_kWh=5,
                                                                 max_abs_battery_power_kW=5,
                                                                 break_even=(16.99, 17.01)),
                         appliance=SwitchableAppliance()),
                ]
            ),

            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=15),
                 appliance=SimpleAppliance()),

        ],
        config=config
    )
    return area
