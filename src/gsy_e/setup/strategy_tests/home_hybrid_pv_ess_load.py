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
from gsy_e.models.strategy.storage import StorageStrategy
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy

'''
This setup file is being modified to mimic a typical
modern household having a hybrid PV-ESS system.
Bug: The PV should be selling power cheaper than the Commercial Producer, but it"s not selling
'''
# TODO: Try to reenact the bug behaviour and add an integration test.


def get_setup(config):
    config.set_market_maker_rate(30)
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 General Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_of_day=list(
                                                                           range(0, 24)),
                                                                       final_buying_rate=14)
                         ),
                    Area("H1 Storage1", strategy=StorageStrategy(energy_rate_decrease_per_update=7,
                                                                 battery_capacity_kWh=1.2,
                                                                 max_abs_battery_power_kW=5,
                                                                 final_buying_rate=12,
                                                                 final_selling_rate=17.01)
                         ),
                    Area("H1 PV", strategy=PVStrategy(panel_count=4,
                                                      final_selling_rate=5,
                                                      energy_rate_decrease_per_update=7)
                         ),

                ]
            ),
            Area("Commercial Energy Producer",
                 strategy=CommercialStrategy(energy_rate=15)
                 ),
        ],
        config=config
    )
    return area
