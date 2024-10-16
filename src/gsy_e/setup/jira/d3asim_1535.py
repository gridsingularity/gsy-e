"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange
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

"""
This setup file should fail because leaf areas can not have children.
Leaf areas are areas that have a strategy.
"""


def get_setup(config):
    area = Area(
        "Grid",
        [
            Area("Finite Power Plant", strategy=FinitePowerPlant(energy_rate=30,
                                                                 max_available_power_kW=100)
                 ),
            Area("Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                    hrs_of_day=list(range(8, 18))),
                 children=[
                    Area("Forbidden Load", strategy=LoadHoursStrategy(avg_power_W=100))
                ]),
        ],
        config=config
    )
    return area
