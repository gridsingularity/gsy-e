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


"""
Setup file for displaying LoadHoursStrategy.
Test parsing of LoadHoursStrategy max_energy_rate as dictionary.
"""

user_profile_int = {
        0: 32,
        6: 35,
        12: 35,
        18: 35
    }

user_profile_str = "{'00:00': 32, '06:00': 35, '12:00': 35, '12:00': 35}"


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load 1',
                         strategy=LoadHoursStrategy(avg_power_W=200, hrs_of_day=list(range(0, 24)),
                                                    max_energy_rate=user_profile_int),
                         appliance=SwitchableAppliance()),
                    Area('H1 General Load 2',
                         strategy=LoadHoursStrategy(avg_power_W=200, hrs_of_day=list(range(0, 24)),
                                                    max_energy_rate=user_profile_str),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=34),
                 appliance=SimpleAppliance()
                 ),
        ],
        config=config
    )
    return area
