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
        [*[Area("House " + str(i), [
            Area(f"H{i} General Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                  hrs_of_day=list(range(24))),
                 ),
            Area(f"H{i} PV",
                 strategy=PVStrategy(6, 80)),
            Area(f"H{i} Storage",
                 strategy=StorageStrategy(initial_soc=50),
                 )
        ]) for i in range(1, 1000)],
         Area("Commercial Energy Producer",
              strategy=CommercialStrategy(energy_rate=30)
              ),
        ],
        config=config
    )
    return area
