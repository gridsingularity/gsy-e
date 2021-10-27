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
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
from gsy_framework.constants_limits import ConstSettings


def get_setup(config):
    ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS = True
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 General Load", strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=18,
                                                                       hrs_of_day=list(
                                                                           range(0, 18)),
                                                                       final_buying_rate=35)
                         ),
                    Area("H1 Storage1", strategy=StorageStrategy(initial_soc=100)
                         ),
                    Area("H1 Storage2", strategy=StorageStrategy(initial_soc=100)
                         ),
                ],
                grid_fee_percentage=0, grid_fee_constant=0,
            ),
            Area(
                "House 2",
                [
                    Area("H2 General Load", strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=24,
                                                                       hrs_of_day=list(
                                                                           range(0, 24)),
                                                                       final_buying_rate=35)
                         ),
                    Area("H2 PV", strategy=PVStrategy(4, 80)
                         ),

                ],
                grid_fee_percentage=0, grid_fee_constant=0,
            ),
            Area("Cell Tower", strategy=LoadHoursStrategy(avg_power_W=100,
                                                          hrs_per_day=24,
                                                          hrs_of_day=list(range(0, 24)),
                                                          final_buying_rate=35)
                 ),

        ],
        config=config
    )
    return area
