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
from gsy_framework.constants_limits import ConstSettings
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
'''
Setup load + DSO
Test for constant_fee in pay as bid
'''


def get_setup(config):
    ConstSettings.MASettings.GRID_FEE_TYPE = 1
    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 3
    ConstSettings.MASettings.MARKET_TYPE = 2

    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 General Load", strategy=LoadHoursStrategy(avg_power_W=4000,
                                                                       hrs_of_day=list(
                                                                           range(12, 13)),
                                                                       initial_buying_rate=45,
                                                                       final_buying_rate=45,
                                                                       fit_to_limit=True)
                         ),
                ], grid_fee_percentage=0, grid_fee_constant=0,
            ),

            Area("DSO", strategy=InfiniteBusStrategy(energy_buy_rate=5, energy_sell_rate=30),
                 )
        ],
        config=config, grid_fee_percentage=0, grid_fee_constant=45,
    )
    return area
