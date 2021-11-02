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
from gsy_e.models.area import Area
from gsy_e.models.strategy.predefined_wind import WindUserProfileStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.gsy_e_core.util import d3a_path
import os


"""
Setup file for displaying WindUserProfileStrategy.
"""

user_profile_path = os.path.join(d3a_path, "resources/Solar_Curve_W_sunny.csv")


def get_setup(config):
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 General Load", strategy=LoadHoursStrategy(avg_power_W=500,
                                                                       hrs_per_day=12,
                                                                       hrs_of_day=list(
                                                                           range(7, 20)))
                         ),
                ]
            ),
            Area("Wind Turbine", strategy=WindUserProfileStrategy(power_profile=user_profile_path)
                 ),
        ],
        config=config
    )
    return area
