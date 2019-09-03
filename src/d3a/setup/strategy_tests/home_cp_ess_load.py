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


'''
This setup file is being modified to mimic a home with load and ess and a commercial producer
The bug here is that the ESS is charging too fast from the commercial producer (it becomes
fully charged in one slot bypassing the max abs battery power
'''


def get_setup(config):
    config.read_market_maker_rate(30)
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_per_day=24,
                                                                       hrs_of_day=list(
                                                                           range(0, 24)),
                                                                       final_buying_rate=25),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(initial_soc=50,
                                                                 fit_to_limit=False,
                                                                 energy_rate_change_per_update=7,
                                                                 battery_capacity_kWh=1.2,
                                                                 max_abs_battery_power_kW=0.05,
                                                                 initial_buying_rate=0,
                                                                 final_buying_rate=16,
                                                                 final_selling_rate=17.01),
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
