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
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.pv import PVStrategy
from d3a.models.appliance.pv import PVAppliance


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=23,
                                                                       hrs_of_day=list(
                                                                           range(0, 23)),
                                                                       final_buying_rate=25),
                         appliance=SwitchableAppliance()),
                    Area('H1 PV', strategy=PVStrategy(panel_count=4,
                                                      initial_rate_option=3,
                                                      initial_selling_rate=23.0,
                                                      final_selling_rate=23.0),
                         appliance=PVAppliance()),
                ]
            ),
            Area('Infinite Bus', strategy=InfiniteBusStrategy(energy_buy_rate=24,
                                                              energy_sell_rate=24),
                 appliance=SimpleAppliance()
                 ),

        ],
        config=config
    )
    return area
