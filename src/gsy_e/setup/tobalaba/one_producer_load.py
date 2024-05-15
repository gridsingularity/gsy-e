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
from gsy_e.models.strategy.finite_power_plant import FinitePowerPlant
from gsy_e.models.strategy.load_hours import LoadHoursStrategy


def get_setup(config):
    area = Area(
        "Grid",
        [
            Area("Cell Tower", strategy=LoadHoursStrategy(avg_power_W=50)
                 ),
            Area("Commercial Energy Producer",
                 strategy=FinitePowerPlant(energy_rate=30,
                                           max_available_power_kW=100)
                 ),

        ],
        config=config
    )
    return area
