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
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.appliance.simple import SimpleAppliance
from d3a.d3a_core.util import d3a_path
import os


"""
Setup file for displaying DefinedLoadStrategy.
DefinedLoadStrategy Strategy requires daily_load_profile and
final_buying_rate is optional.
"""

profile_path = os.path.join(d3a_path, "resources/LOAD_DATA_1.csv")


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 DefinedLoad',
                         strategy=DefinedLoadStrategy(daily_load_profile=profile_path,
                                                      final_buying_rate=36),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area('Commercial Energy Producer', strategy=CommercialStrategy(),
                 appliance=SimpleAppliance()
                 ),
        ],
        config=config
    )
    return area
