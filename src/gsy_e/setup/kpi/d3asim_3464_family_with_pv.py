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
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.finite_power_plant import FinitePowerPlant


def get_setup(config):

    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.MASettings.MIN_OFFER_AGE = 0
    ConstSettings.MASettings.MIN_BID_AGE = 0

    area = Area(
        "Grid",
        [
            Area(
                "Community",
                [
                    Area("Family 2 children with PV",
                         [
                            Area("Family General Load", strategy=LoadHoursStrategy(
                                avg_power_W=2161, hrs_of_day=list(range(24)),
                                initial_buying_rate=27.895, final_buying_rate=27.895,
                                fit_to_limit=True)),
                            Area("Family PV", strategy=PVStrategy(
                                capacity_kW=17.985, panel_count=1,
                                initial_selling_rate=5, final_selling_rate=5))
                         ]),
                    Area("Community PP", strategy=FinitePowerPlant(
                        max_available_power_kW=5, energy_rate=1
                    ))

                ], grid_fee_constant=4.0),
            Area("DSO", strategy=InfiniteBusStrategy(energy_buy_rate=20, energy_sell_rate=22))
        ],
        config=config, grid_fee_constant=4.0,
    )
    return area
