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
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy


def get_setup(config):
    ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS = True
    ConstSettings.SettlementMarketSettings.RELATIVE_STD_FROM_FORECAST_FLOAT = 90
    ConstSettings.SettlementMarketSettings.MAX_AGE_SETTLEMENT_MARKET_HOURS = 1
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.MASettings.BID_OFFER_MATCH_TYPE = BidOfferMatchAlgoEnum.PAY_AS_BID.value
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 General Load", strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_of_day=list(
                                                                           range(8, 18)),
                                                                       final_buying_rate=35)
                         ),
                    Area("H1 PV", strategy=PVStrategy()
                         ),
                ],
            ),
        ],
        config=config
    )
    return area
