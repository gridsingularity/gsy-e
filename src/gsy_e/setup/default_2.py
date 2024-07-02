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
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.storage import StorageStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy


def get_setup(config):
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 General Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_of_day=list(
                                                                           range(12, 20)),
                                                                       final_buying_rate=29)
                         ),
                    Area("H1 Lighting", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                   hrs_of_day=list(range(12, 16)))
                         ),
                    Area("H1 Storage1", strategy=StorageStrategy(initial_soc=50)
                         ),
                    Area("H1 Storage2", strategy=StorageStrategy(initial_soc=50)
                         ),
                ]
            ),
            Area(
                "House 2",
                [
                    Area("H2 General Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_of_day=list(
                                                                           range(12, 18)),
                                                                       final_buying_rate=50)
                         ),
                    Area("H2 Lighting", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                   hrs_of_day=list(range(12, 16)))
                         ),
                    Area("H2 PV", strategy=PVStrategy(2, 80)
                         ),
                ]
            ),
            Area(
                "House 3",
                [
                    Area("H3 General Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_of_day=list(
                                                                           range(12, 13)))
                         ),
                    Area("H3 Lighting", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                   hrs_of_day=list(range(12, 16)))
                         ),
                    Area("H3 PV", strategy=PVStrategy(4, 60)
                         ),
                ]
            ),
            Area(
                "House 4",
                [
                    Area("H4 General Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_of_day=list(
                                                                           range(12, 13)))
                         ),
                    Area("H4 Lighting", strategy=LoadHoursStrategy(avg_power_W=200,
                                                                   hrs_of_day=list(range(12, 16)))
                         ),
                    Area("H4 TV", strategy=LoadHoursStrategy(avg_power_W=100,
                                                             hrs_of_day=list(range(14, 18)))
                         ),
                    Area("H4 PV", strategy=PVStrategy(4, 60)
                         ),
                    Area("H4 Storage1", strategy=StorageStrategy(initial_soc=50)
                         ),
                    Area("H4 Storage2", strategy=StorageStrategy(initial_soc=50)
                         ),
                ]
            ),
            Area(
                "House 5",
                [
                    Area("H5 General Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_of_day=list(
                                                                           range(12, 13)))
                         ),
                    Area("H5 Lighting", strategy=LoadHoursStrategy(avg_power_W=200,
                                                                   hrs_of_day=list(range(12, 16)))
                         ),
                    Area("H5 TV", strategy=LoadHoursStrategy(avg_power_W=100,
                                                             hrs_of_day=list(range(10, 15)))
                         ),
                    Area("H5 PV", strategy=PVStrategy(5, 60),
                         ),
                    Area("H5 Storage1", strategy=StorageStrategy(initial_soc=50)
                         ),
                    Area("H5 Storage2", strategy=StorageStrategy(initial_soc=50)
                         ),
                ]
            ),

            Area("Commercial Energy Producer",
                 strategy=CommercialStrategy(energy_rate=30)
                 ),

            Area("Cell Tower", strategy=LoadHoursStrategy(avg_power_W=100,
                                                          hrs_of_day=list(range(0, 24)))
                 )
        ],
        config=config
    )
    return area
