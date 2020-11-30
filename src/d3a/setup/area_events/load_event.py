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
from d3a.models.area.events import StrategyEvents
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a_interface.constants_limits import ConstSettings


def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    area = Area(
        'Grid',
        children=[
            Area(
                'House 1',
                children=[
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=24,
                                                                       hrs_of_day=list(
                                                                           range(0, 24)),
                                                                       initial_buying_rate=1,
                                                                       final_buying_rate=37),
                         event_list=[StrategyEvents(12, {'avg_power_W': 400,
                                                         'hrs_per_day': 22,
                                                         'hrs_of_day': range(0, 22)}),
                                     StrategyEvents(15, {'initial_buying_rate': 24,
                                                         'fit_to_limit': False,
                                                         'update_interval': 10,
                                                         'energy_rate_increase_per_update': 1})]
                         )
                ]
            ),
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=30)
                 ),

        ],
        config=config
    )
    return area
