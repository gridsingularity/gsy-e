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
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy

# This setup file is used to test that if a Load asset has the fit to
# limit box checked, there will be no unmatched load, when the final
# buying rate coincides with the one of the market maker.


def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 1

    area = Area(
        "Grid Market",
        [
            Area(
                "Home",
                [
                    Area("Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                            hrs_per_day=24,
                                                            hrs_of_day=list(range(0, 24)),
                                                            initial_buying_rate=0,
                                                            fit_to_limit=True,
                                                            use_market_maker_rate=True,
                                                            )
                         ),
                ],
                grid_fee_percentage=40
            ),
            Area("Market Maker", strategy=InfiniteBusStrategy(
                energy_sell_rate=30, energy_buy_rate=0)
                 )
        ],
        config=config
    )
    return area
