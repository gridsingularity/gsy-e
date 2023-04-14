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
from gsy_e.models.strategy.predefined_pv import PVPredefinedStrategy
from gsy_e.models.strategy.electrolyzer import ElectrolyzerStrategy
from gsy_e.gsy_e_core.util import gsye_root_path
import os

electrolizer_profile_file = os.path.join(gsye_root_path, "resources",
                                         "Electrolyzer_Discharge_Profile_kg.csv")


def get_setup(config):
    area = Area(
        "Grid",
        [
            Area("Electrolyzer", strategy=ElectrolyzerStrategy(
                                          discharge_profile=electrolizer_profile_file,
                                          conversion_factor_kg_to_kWh=50,
                                          reservoir_capacity_kg=56.0,
                                          reservoir_initial_capacity_kg=10,
                                          production_rate_kg_h=2.8
                    )),

            Area("PV", strategy=PVPredefinedStrategy(panel_count=1)),

            Area("Commercial Energy Producer", strategy=CommercialStrategy(),
                 )
        ],
        config=config
    )
    return area
