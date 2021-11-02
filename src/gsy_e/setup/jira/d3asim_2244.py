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
from gsy_e.models.area import Area
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.market_maker_strategy import MarketMakerStrategy
from gsy_e.models.strategy.predefined_pv import PVPredefinedStrategy
from gsy_framework.constants_limits import ConstSettings


def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    area = Area(
        "Grid",
        [
            Area("Market Maker", strategy=MarketMakerStrategy(energy_rate=30,
                                                              grid_connected=True)
                 ),
            Area(
                "House 1",
                [
                    Area("H1 PV", strategy=PVPredefinedStrategy(capacity_kW=0.25,
                                                                cloud_coverage=0,
                                                                use_market_maker_rate=True)
                         ),
                    Area("H1 General Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_per_day=9,
                                                                       hrs_of_day=list(
                                                                           range(15, 24)),
                                                                       final_buying_rate=0,
                                                                       use_market_maker_rate=True)
                         ),
                ]
            ),
        ],
        config=config
    )
    return area
