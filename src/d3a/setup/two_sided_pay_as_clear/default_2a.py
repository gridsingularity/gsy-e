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
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a_interface.constants_limits import ConstSettings


def get_setup(config):

    ConstSettings.IAASettings.MARKET_TYPE = 3
    # ConstSettings.GeneralSettings.SUPPLY_DEMAND_PLOTS = False
    ConstSettings.GeneralSettings.MARKET_CLEARING_FREQUENCY_PER_SLOT = 3
    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 5

    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_per_day=6,
                                                                       hrs_of_day=list(
                                                                           range(12, 18)),
                                                                       initial_buying_rate=35,
                                                                       final_buying_rate=35),
                         ),
                    Area('H1 Storage1', strategy=StorageStrategy(initial_soc=50),
                         ),
                    Area('H1 Storage2', strategy=StorageStrategy(initial_soc=50),
                         ),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 General Load', strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_per_day=4,
                                                                       hrs_of_day=list(range(12,
                                                                                             16)),
                                                                       final_buying_rate=35),
                         ),
                    Area('H2 PV', strategy=PVStrategy(4),
                         ),
                    Area('H2 CEP',
                         strategy=CommercialStrategy(energy_rate=10),
                         ),

                ]
            ),
            Area('Cell Tower', strategy=LoadHoursStrategy(avg_power_W=100,
                                                          hrs_per_day=24,
                                                          hrs_of_day=list(range(0, 24)),
                                                          final_buying_rate=35),
                 ),
        ],
        config=config
    )
    return area
