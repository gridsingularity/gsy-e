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
# from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.pv import PVStrategy
# from gsy_e.models.strategy.storage import StorageStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy


def get_setup(config):
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 General Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_per_day=4,
                                                                       hrs_of_day=list(
                                                                           range(12, 16))),
                         ),
                ]
            ),
            Area(
                "House 2",
                [
                    Area("H2 General Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_per_day=4,
                                                                       hrs_of_day=list(
                                                                           range(12, 16))),
                         ),
                    Area("H2 PV", strategy=PVStrategy(1, 80),
                         ),
                ]
            ),

            # Area("Commercial Energy Producer",
            #      strategy=CommercialStrategy(energy_range_wh=(40, 120), energy_price=30),
            #
            #      ),

        ],
        config=config
    )
    return area
