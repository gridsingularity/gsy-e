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
from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.predefined_wind import WindUserProfileStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.d3a_core.util import d3a_path
import os


"""
Setup file for displaying WindUserProfileStrategy.
WindUserProfileStrategy Strategy requires power_profile, risk &
lower selling rate threshold.
"""

user_profile_path = os.path.join(d3a_path, "resources/Solar_Curve_W_sunny.csv")


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=500,
                                                                       hrs_per_day=12,
                                                                       hrs_of_day=list(
                                                                           range(7, 20))),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area('Wind Turbine', strategy=WindUserProfileStrategy(power_profile=user_profile_path,
                                                                  risk=80),
                 appliance=PVAppliance()),
        ],
        config=config
    )
    return area
