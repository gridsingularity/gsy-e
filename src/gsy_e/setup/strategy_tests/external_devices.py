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
from gsy_framework.enums import BidOfferMatchAlgoEnum

from gsy_e.models.area import Area
from gsy_e.models.strategy.external_strategies.load import (LoadHoursExternalStrategy,
                                                            LoadHoursForecastExternalStrategy)
from gsy_e.models.strategy.external_strategies.pv import PVExternalStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.storage import StorageStrategy


def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.MASettings.MIN_BID_AGE = 0
    ConstSettings.MASettings.BID_OFFER_MATCH_TYPE = \
        BidOfferMatchAlgoEnum.PAY_AS_CLEAR.value
    ConstSettings.MASettings.MIN_OFFER_AGE = 0
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 General Load", strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_of_day=list(
                                                                           range(12, 18)),
                                                                       final_buying_rate=35)
                         ),
                    Area("H1 Storage1", strategy=StorageStrategy(initial_soc=100,
                                                                 battery_capacity_kWh=20)
                         ),
                    Area("H1 Storage2", strategy=StorageStrategy(initial_soc=100,
                                                                 battery_capacity_kWh=20)
                         ),
                ],
            ),
            Area(
                "House 2",
                [
                    Area("load", strategy=LoadHoursExternalStrategy(
                        avg_power_W=200, hrs_of_day=list(range(0, 24)),
                        final_buying_rate=35)
                         ),
                    Area("pv", strategy=PVExternalStrategy(panel_count=4)
                         ),
                    Area("forecast-measurement-load", strategy=LoadHoursForecastExternalStrategy(
                        final_buying_rate=35)
                         ),

                ], external_connection_available=True,
            ),
            Area("Cell Tower", strategy=LoadHoursStrategy(avg_power_W=100,
                                                          hrs_of_day=list(range(0, 24)),
                                                          final_buying_rate=35)
                 ),
        ],
        config=config
    )
    return area
