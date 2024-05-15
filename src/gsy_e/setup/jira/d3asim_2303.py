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
from gsy_e.models.strategy.finite_power_plant import FinitePowerPlant
from gsy_e.models.strategy.market_maker_strategy import MarketMakerStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy


def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = 2
    area = Area(
        "Grid",
        [
            Area(
                "Community",
                [
                    Area("H1",
                         [
                            Area("Load", strategy=LoadHoursStrategy(avg_power_W=1000,
                                                                    hrs_of_day=list(
                                                                       range(10, 11)),
                                                                    initial_buying_rate=60,
                                                                    final_buying_rate=60,
                                                                    update_interval=1)
                                 ),
                         ], grid_fee_constant=2)
                ],
                grid_fee_constant=3,
            ),
            Area(
                "DSO",
                [
                    Area("Power Plant", strategy=FinitePowerPlant(energy_rate=30,
                                                                  max_available_power_kW=1000)
                         ),
                ],
                grid_fee_constant=10,
            ),
            Area("Market Maker", strategy=MarketMakerStrategy(grid_connected=True, energy_rate=50)
                 ),
        ], grid_fee_constant=10,
        config=config
    )
    return area
