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
import os
from d3a.d3a_core.util import d3a_path
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.electrolyzer import ElectrolyzerStrategy


discharge_path = os.path.join(d3a_path, "resources/Electrolyzer_Discharge_Profile_kg.csv")


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 Electrolyser',
                         strategy=ElectrolyzerStrategy(discharge_profile=discharge_path,
                                                       production_rate_kg_h=4.0),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=20),
                 appliance=SimpleAppliance()
                 ),

        ],
        config=config
    )
    return area
