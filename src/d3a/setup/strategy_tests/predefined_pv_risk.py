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
from d3a.models.appliance.pv import PVAppliance
# from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
# from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy
# from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy

"""
Setup file for displaying PVPredefinedStrategy.
PredefinedPV Strategy requires risk, panel count, lower selling rate threshold &
cloud_coverage parameters.
Because the risk parameter is required, this is the risk or percentage based PV strategy
There is another setup file in which Faizan has detailed how the risk based strategy works
which will be added
"""


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=500,
                                                                       hrs_per_day=12,
                                                                       hrs_of_day=list(
                                                                           range(7, 20))),
                         appliance=SwitchableAppliance()),
                    Area('H1 PV', strategy=PVPredefinedStrategy(panel_count=1,
                                                                risk=80,
                                                                cloud_coverage=2),
                         appliance=PVAppliance()),
                ]
            ),
        ],
        config=config
    )
    return area
