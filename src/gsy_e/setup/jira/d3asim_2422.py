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
from gsy_e.models.strategy.market_maker_strategy import MarketMakerStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.storage import StorageStrategy


def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.GeneralSettings.EXPORT_ENERGY_TRADE_PROFILE_HR = True
    ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR = True

    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 General Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_of_day=list(
                                                                           range(12, 18)),
                                                                       final_buying_rate=30,
                                                                       fit_to_limit=True,
                                                                       update_interval=1)
                         ),
                    Area("H1 Storage1", strategy=StorageStrategy(initial_soc=50,
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
            Area(
                "House 2",
                [
                    Area("H2 General Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_of_day=list(range(12,
                                                                                             16)),
                                                                       final_buying_rate=30,
                                                                       fit_to_limit=True,
                                                                       update_interval=1)
                         ),
                    Area("H2 PV", strategy=PVStrategy(4,
                                                      initial_selling_rate=30,
                                                      final_selling_rate=0,
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
                                            update_interval=1)
                 ),
            Area("Market Maker", strategy=MarketMakerStrategy(energy_rate=30,
                                                              grid_connected=True)
                 ),

        ],
        config=config
    )
    return area
