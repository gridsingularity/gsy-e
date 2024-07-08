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
from gsy_e.models.strategy.storage import StorageStrategy
from gsy_framework.constants_limits import ConstSettings
from gsy_e.models.strategy.load_hours import LoadHoursStrategy


def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR = True

    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [

                    Area("H1 Storage1", strategy=StorageStrategy(initial_soc=100,
                                                                 min_allowed_soc=10,
                                                                 battery_capacity_kWh=1.2,
                                                                 max_abs_battery_power_kW=5,
                                                                 initial_selling_rate=30,
                                                                 final_buying_rate=25,
                                                                 final_selling_rate=25.1,
                                                                 initial_buying_rate=0,
                                                                 fit_to_limit=True,
                                                                 update_interval=1)
                         ),
                ]
            ),
            Area("Cell Tower",
                 strategy=LoadHoursStrategy(avg_power_W=100,
                                            hrs_of_day=list(range(0, 24)),
                                            final_buying_rate=30,
                                            fit_to_limit=True,
                                            update_interval=3)
                 ),
        ],
        config=config
    )
    return area
