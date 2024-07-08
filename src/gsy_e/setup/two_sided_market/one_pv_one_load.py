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
from pendulum import duration

from gsy_e.models.area import Area
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_framework.constants_limits import ConstSettings


def get_setup(config):
    # Two sided market
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.PVSettings.FINAL_SELLING_RATE = 0
    ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE = 30
    ConstSettings.LoadSettings.INITIAL_BUYING_RATE = 0
    ConstSettings.LoadSettings.FINAL_BUYING_RATE = 30

    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 General Load", strategy=LoadHoursStrategy(
                        avg_power_W=200,
                        hrs_of_day=list(range(9, 15)),
                        initial_buying_rate=ConstSettings.LoadSettings.INITIAL_BUYING_RATE,
                        final_buying_rate=ConstSettings.LoadSettings.FINAL_BUYING_RATE,
                        fit_to_limit=True, update_interval=duration(minutes=14)
                    )),
                ]
            ),
            Area(
                "House 2",
                [
                    Area("H2 PV",
                         strategy=PVStrategy(panel_count=4, initial_selling_rate=30,
                                             final_selling_rate=0, fit_to_limit=True,
                                             update_interval=duration(minutes=5))
                         ),

                ]
            ),
        ],
        config=config
    )
    return area
