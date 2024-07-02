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
from gsy_e.models.strategy.external_strategies.storage import StorageExternalStrategy

ConstSettings.MASettings.MARKET_TYPE = 2


def get_setup(config):
    """Return the setup to be used for the simulation."""

    ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS = 1
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("load", strategy=LoadHoursStrategy(
                        hrs_of_day=list(range(2, 24)), avg_power_W=4000,
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
