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
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy
from d3a_interface.constants_limits import ConstSettings
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.appliance.simple import SimpleAppliance

# Setup for a microgrid + DSO


def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 1
    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 5

    Houses_initial_buying_rate = 6
    Houses_final_buying_rate = 30

    area = Area(
        'Grid',
        [
            Area(
                'Microgrid',
                [
                    Area(
                        'House 1',
                        [
                            Area('H1 General Load', strategy=LoadHoursStrategy(
                                avg_power_W=100,
                                hrs_per_day=5, hrs_of_day=[9, 10, 11, 12, 13, 14, 15, 16],
                                initial_buying_rate=Houses_initial_buying_rate,
                                final_buying_rate=Houses_final_buying_rate),
                                 appliance=SwitchableAppliance()),

                            Area('H1 PV', strategy=PVStrategy(panel_count=3,
                                                              max_panel_power_W=250,  # to test
                                                              initial_selling_rate=30,
                                                              final_selling_rate=0),
                                 appliance=PVAppliance()),

                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),


                    Area(
                        'House 2',
                        [
                            Area('H2 General Load', strategy=LoadHoursStrategy(
                                avg_power_W=100,
                                hrs_per_day=5, hrs_of_day=[9, 10, 11, 12, 13, 14, 15, 16],
                                initial_buying_rate=Houses_initial_buying_rate,
                                final_buying_rate=Houses_final_buying_rate),
                                 appliance=SwitchableAppliance()),

                            Area('H2 PV', strategy=PVStrategy(panel_count=4,
                                                              max_panel_power_W=250,
                                                              initial_selling_rate=30,
                                                              final_selling_rate=0),
                                 appliance=PVAppliance()),

                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                ],),

            Area('DSO', strategy=InfiniteBusStrategy(energy_buy_rate=5),
                 appliance=SimpleAppliance()),

        ],
        config=config, grid_fee_percentage=0, transfer_fee_const=0,
    )
    return area
