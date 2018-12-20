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
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy


'''
This setup file test the correct parsing of ESS break_even range.
'''


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=24,
                                                                       hrs_of_day=list(
                                                                           range(0, 24)),
                                                                       max_energy_rate=25),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(risk=10,
                                                                 initial_capacity_kWh=0.6,
                                                                 initial_rate_option=2,
                                                                 energy_rate_decrease_option=1,
                                                                 energy_rate_decrease_per_update=3,
                                                                 battery_capacity_kWh=1.2,
                                                                 max_abs_battery_power_kW=5,
                                                                 break_even=(16.99, 17.01)),
                         appliance=SwitchableAppliance()),
                    Area('H1 PV', strategy=PVStrategy(panel_count=4,
                                                      risk=10,
                                                      final_selling_rate=5,
                                                      initial_rate_option=2,
                                                      energy_rate_decrease_option=1,
                                                      energy_rate_decrease_per_update=3),
                         appliance=PVAppliance()),

                ]
            ),
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=30),
                 appliance=SimpleAppliance()),
        ],
        config=config
    )
    return area
