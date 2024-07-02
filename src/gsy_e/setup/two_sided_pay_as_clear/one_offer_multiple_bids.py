"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange
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
from gsy_e.models.strategy.finite_power_plant import FinitePowerPlant
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import BidOfferMatchAlgoEnum


def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.MASettings.BID_OFFER_MATCH_TYPE = \
        BidOfferMatchAlgoEnum.PAY_AS_CLEAR.value

    area = Area(
        "Grid",
        [
            Area(
                "Energy Community",
                [
                    Area("Load 1", strategy=LoadHoursStrategy(
                        avg_power_W=500, hrs_of_day=list(range(24)),
                        initial_buying_rate=10, final_buying_rate=10),
                         ),
                    Area("Load 2", strategy=LoadHoursStrategy(
                        avg_power_W=500, hrs_of_day=list(range(24)),
                        initial_buying_rate=15, final_buying_rate=15),
                         ),
                    Area("Load 3", strategy=LoadHoursStrategy(
                        avg_power_W=500, hrs_of_day=list(range(24)),
                        initial_buying_rate=30, final_buying_rate=30),
                         ),
                    Area("Local Supply",
                         strategy=FinitePowerPlant(energy_rate=10, max_available_power_kW=1.0),
                         ),
                ],
            ),
        ],
        config=config
    )
    return area
