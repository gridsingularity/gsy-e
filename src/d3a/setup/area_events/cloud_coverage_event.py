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
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.area.event_types import ConfigEvents
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy


def get_setup(config):
    config.cloud_coverage = 0
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                event_list=[ConfigEvents(12, {'cloud_coverage': 1})],
                children=[
                    Area('H1 PV', strategy=PVPredefinedStrategy(),
                         appliance=PVAppliance()),
                ]
            ),
            Area(
                'House 2',
                event_list=[ConfigEvents(12, {'cloud_coverage': 2})],
                children=[
                    Area('H2 PV', strategy=PVPredefinedStrategy(),
                         appliance=PVAppliance()),

                ]
            ),
            Area('Grid Load', strategy=LoadHoursStrategy(avg_power_W=100000,
                                                         hrs_per_day=24,
                                                         hrs_of_day=list(
                                                             range(0, 24)),
                                                         final_buying_rate=35),
                 appliance=SwitchableAppliance()),
        ],
        config=config
    )
    return area
