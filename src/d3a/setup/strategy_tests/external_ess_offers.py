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
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.external_strategies.storage import StorageExternalStrategy
from gsy_framework.constants_limits import ConstSettings

ConstSettings.IAASettings.MARKET_TYPE = 2


def get_setup(config):
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("load", strategy=LoadHoursStrategy(
                        hrs_of_day=list(range(2, 24)), hrs_per_day=20, avg_power_W=4000,
                        initial_buying_rate=0, final_buying_rate=30),
                         ),
                    Area("storage", strategy=StorageExternalStrategy(
                        initial_soc=50, battery_capacity_kWh=20, max_abs_battery_power_kW=1
                    ),
                         ),
                ],
            ),
        ],
        config=config
    )
    return area
