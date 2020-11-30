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
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy


def get_setup(config):
    area = Area(
        'Grid',
        children=[
            Area(
                'House 1',
                children=[
                    Area('H2 PV', strategy=PVStrategy(panel_count=1,
                                                      initial_selling_rate=80),
                         event_list=[StrategyEvents(12, {'panel_count': 5,
                                                         'max_panel_power_W': 320})])
                ]
            ),
            Area('Grid Load', strategy=LoadHoursStrategy(avg_power_W=10000,
                                                         hrs_per_day=24,
                                                         hrs_of_day=list(
                                                             range(0, 24)),
                                                         final_buying_rate=35)
                 )
        ],
        config=config
    )
    return area
