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
from gsy_e.models.strategy.finite_power_plant import FinitePowerPlant
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import BidOfferMatchAlgoEnum


def get_setup(config):
    ConstSettings.GeneralSettings.EXPORT_SUPPLY_DEMAND_PLOTS = True
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.MASettings.BID_OFFER_MATCH_TYPE = \
        BidOfferMatchAlgoEnum.PAY_AS_CLEAR.value
    ConstSettings.MASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM = 1
    ConstSettings.GeneralSettings.MARKET_CLEARING_FREQUENCY_PER_SLOT = 1
    ConstSettings.MASettings.MIN_OFFER_AGE = 0
    ConstSettings.MASettings.MIN_BID_AGE = 0

    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 General Load1", strategy=LoadHoursStrategy(
                        avg_power_W=100, hrs_of_day=list(range(24)),
                        initial_buying_rate=28.8, fit_to_limit=False,
                        energy_rate_increase_per_update=0),
                         ),
                    Area("H1 General Load2", strategy=LoadHoursStrategy(
                        avg_power_W=100, hrs_of_day=list(range(24)),
                        initial_buying_rate=18.8, fit_to_limit=False,
                        energy_rate_increase_per_update=0),
                         ),
                    Area("H1 General Load3", strategy=LoadHoursStrategy(
                        avg_power_W=100, hrs_of_day=list(range(24)),
                        initial_buying_rate=8.8, fit_to_limit=False,
                        energy_rate_increase_per_update=0),
                         ),
                    Area("H1 CEP1",
                         strategy=FinitePowerPlant(energy_rate=5.1, max_available_power_kW=0.1),
                         ),
                    Area("H1 CEP2",
                         strategy=FinitePowerPlant(energy_rate=15.5, max_available_power_kW=0.1),
                         ),
                    Area("H1 CEP3",
                         strategy=FinitePowerPlant(energy_rate=25.001, max_available_power_kW=0.1),
                         ),
                    Area("H1 CEP4",
                         strategy=FinitePowerPlant(energy_rate=28.001, max_available_power_kW=0.1),
                         ),
                ]
            ),
        ],
        config=config
    )
    return area
