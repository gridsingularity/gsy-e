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
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.predefined_load import DefinedLoadStrategy
from gsy_e.gsy_e_core.util import gsye_root_path
import os

"""
Setup file for displaying DefinedLoadStrategy.
DefinedLoadStrategy Strategy requires daily_load_profile and
final_buying_rate is optional.
"""

profile_path = os.path.join(gsye_root_path, "resources/LOAD_DATA_1.csv")


def get_setup(config):
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 DefinedLoad",
                         strategy=DefinedLoadStrategy(daily_load_profile=profile_path,
                                                      final_buying_rate=36)
                         ),
                ]
            ),
            Area("Commercial Energy Producer", strategy=CommercialStrategy()
                 ),
        ],
        config=config
    )
    return area
