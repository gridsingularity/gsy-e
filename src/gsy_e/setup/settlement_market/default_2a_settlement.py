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
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import SpotMarketTypeEnum

from gsy_e.models.area import Area
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.storage import StorageStrategy


def get_setup(config):
    ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS = True
    ConstSettings.IAASettings.MARKET_TYPE = SpotMarketTypeEnum.TWO_SIDED.value

    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 General Load", strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=18,
                                                                       hrs_of_day=list(
                                                                           range(0, 18)),
                                                                       final_buying_rate=35)
                         ),
                    Area("H1 Storage1", strategy=StorageStrategy(initial_soc=50)
                         ),
                    Area("H1 Storage2", strategy=StorageStrategy(initial_soc=50)
                         ),
                ],
                grid_fee_percentage=0, grid_fee_constant=0,
            ),
            Area(
                "House 2",
                [
                    Area("H2 General Load", strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=4,
                                                                       hrs_of_day=list(
                                                                           range(12, 16)),
                                                                       final_buying_rate=35)
                         ),
                    Area("H2 PV", strategy=PVStrategy(capacity_kW=0.16,
                                                      panel_count=4,
                                                      initial_selling_rate=30,
                                                      final_selling_rate=5)
                         ),

                ],
                grid_fee_percentage=0, grid_fee_constant=0,

            ),
            Area("Cell Tower", strategy=LoadHoursStrategy(avg_power_W=100,
                                                          hrs_per_day=24,
                                                          hrs_of_day=list(range(0, 24)),
                                                          final_buying_rate=35)
                 ),

        ],
        config=config
    )
    return area
