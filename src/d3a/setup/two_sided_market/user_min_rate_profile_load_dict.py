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
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.const import ConstSettings


"""
Setup file for displaying LoadHoursStrategy.
Test parsing of LoadHoursStrategy initial_buying_rate as dictionary.
"""

user_profile_int = {
        0: 10,
        6: 15,
        12: 20,
        18: 25,
        21: 30
    }

user_profile_str = "{'00:00': 10, '06:00': 15, '12:00': 20, '18:00': 25, '21:00':30}"


def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load 1',
                         strategy=LoadHoursStrategy(avg_power_W=200, hrs_of_day=list(range(0, 24)),
                                                    initial_buying_rate=user_profile_int,
                                                    final_buying_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H1 General Load 2',
                         strategy=LoadHoursStrategy(avg_power_W=200, hrs_of_day=list(range(0, 24)),
                                                    initial_buying_rate=user_profile_str,
                                                    final_buying_rate=35),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=9),
                 appliance=SimpleAppliance()
                 ),
        ],
        config=config
    )
    return area
