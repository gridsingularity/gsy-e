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
import os
from gsy_e.gsy_e_core.util import gsye_root_path
from gsy_e.models.area import Area
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.electrolyzer import ElectrolyzerStrategy


discharge_path = os.path.join(gsye_root_path, "resources/Electrolyzer_Discharge_Profile_kg.csv")


def get_setup(config):
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 Electrolyser",
                         strategy=ElectrolyzerStrategy(discharge_profile=discharge_path,
                                                       production_rate_kg_h=10.0)
                         ),
                ]
            ),
            Area("Commercial Energy Producer",
                 strategy=CommercialStrategy(energy_rate=20)
                 ),

        ],
        config=config
    )
    return area
