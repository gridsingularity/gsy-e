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
from gsy_e.models.area import Area
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy

"""
This test validates that the average market rate is constant for all hierarchies,
since the PV is the only energy producer.
"""


def get_setup(config):
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 General Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_of_day=list(
                                                                           range(7, 20)))
                         ),
                    Area("H1 PV", strategy=PVStrategy(panel_count=1),
                         )
                ]
            ),
            Area(
                "House 2",
                [
                    Area("H2 General Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_of_day=list(
                                                                           range(12, 16)))
                         ),

                ]
            ),

        ],
        config=config
    )
    return area
