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
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy


def get_setup(config):
    config.update_config_parameters(market_maker_rate=35)
    area = Area(
        "Grid",
        [
            Area("General Load", strategy=LoadHoursStrategy(avg_power_W=200,
                                                            hrs_of_day=list(range(12, 16)),
                                                            final_buying_rate=35)
                 ),
            Area("PV", strategy=PVStrategy(4, 80)),
        ],
        config=config
    )
    return area
