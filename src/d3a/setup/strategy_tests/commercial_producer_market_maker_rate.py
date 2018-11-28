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
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.appliance.simple import SimpleAppliance

"""
Setup file for displaying the infinite power plant strategy.
The infinite power plant strategy follows the market_maker_rate being passed as a
global config parameter. In this setup file, it is intended to validate if
the infinite power plant trades energy at the pre-defined market_maker_rate listed in the file.
"""

market_maker_rate = {
    2: 32, 3: 33, 4: 34, 5: 35, 6: 36, 7: 37, 8: 38,
    9: 37, 10: 38, 11: 39, 14: 34, 15: 33, 16: 32,
    17: 31, 18: 30, 19: 31, 20: 31, 21: 31, 22: 29}


def get_setup(config):
    config.read_market_maker_rate(market_maker_rate)
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=23,
                                                                       hrs_of_day=list(
                                                                           range(0, 23)),
                                                                       max_energy_rate=40),
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
