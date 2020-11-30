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
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a_interface.constants_limits import GlobalConfig, ConstSettings


def get_setup(config):
    config.grid_fee_type = 2
    GlobalConfig.grid_fee_type = 2
    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 5
    area = Area(
        'Grid',
        [
            Area('Neighborhood 1', [
                Area(
                    'House 1',
                    [
                        Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                           hrs_per_day=24,
                                                                           hrs_of_day=list(
                                                                               range(0, 24)),
                                                                           initial_buying_rate=30,
                                                                           final_buying_rate=30)
                             ),
                    ],
                    grid_fee_percentage=0)], grid_fee_percentage=5),
            Area('Neighborhood 2', [
                Area(
                    'House 2',
                    [
                        Area('H2 PV', strategy=PVStrategy(panel_count=10, initial_selling_rate=10,
                                                          final_selling_rate=10),
                             )

                    ],
                    grid_fee_percentage=0

                ),
            ], grid_fee_percentage=5)
        ],
        config=config,
        grid_fee_percentage=10
    )
    return area
