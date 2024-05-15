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
from gsy_framework.constants_limits import ConstSettings

from gsy_e.models.area import Area
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy


def get_setup(config):
    config.grid_fee_type = 1
    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 5
    area = Area(
        "Grid",
        [
            Area("Neighborhood 1", [
                Area(
                    "House 1",
                    [
                        Area("H1 General Load", strategy=LoadHoursStrategy(avg_power_W=200,
                                                                           hrs_of_day=list(
                                                                               range(0, 24)),
                                                                           initial_buying_rate=30,
                                                                           final_buying_rate=30)
                             ),
                    ],
                    grid_fee_constant=0)], grid_fee_constant=1),
            Area("Neighborhood 2", [
                Area(
                    "House 2",
                    [
                        Area("H2 PV", strategy=PVStrategy(panel_count=10, initial_selling_rate=10,
                                                          final_selling_rate=10),
                             )
                    ],
                    grid_fee_constant=0

                ),
            ], grid_fee_constant=1)
        ],
        config=config,
        grid_fee_constant=2
    )
    return area
