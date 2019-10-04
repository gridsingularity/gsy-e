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
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy
from d3a.models.strategy.electrolyzer import ElectrolyzerStrategy
from d3a.d3a_core.util import d3a_path
import os

electrolizer_profile_file = os.path.join(d3a_path, "resources",
                                         "Electrolyzer_Discharge_Profile_kg.csv")


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area('Electrolyzer', strategy=ElectrolyzerStrategy(
                                          discharge_profile=electrolizer_profile_file,
                                          conversion_factor_kg_to_kWh=50,
                                          reservoir_capacity_kg=56.0,
                                          reservoir_initial_capacity_kg=10,
                                          production_rate_kg_h=2.8
                    ), appliance=SwitchableAppliance()),

            Area('PV', strategy=PVPredefinedStrategy(panel_count=1),
                 appliance=PVAppliance()),


            Area("Commercial Energy Producer", strategy=CommercialStrategy(),
                 appliance=SwitchableAppliance()),
        ],
        config=config
    )
    return area
