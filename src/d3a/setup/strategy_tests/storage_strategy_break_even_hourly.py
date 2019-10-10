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
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy

"""
To validate the break even hourly profile the backend plot Energy Trade Profile Of House 1
is required. The energy rates for the storages are displayed in this plot, and these rates
should adhere to the break even hourly profiles that are defined in this module.
Tip: It's interesting to see the change in results from changing the initial_pv_rate_option
between 1(historical average prices) and 2(market maker price).
"""

# This is the profile for the first battery.
final_buying_rate_profile = {
    0: 26.8,
    1: 26.8,
    2: 26.8,
    3: 26.8,
    4: 26.8,
    5: 26.8,
    6: 26.8,
    7: 26.8,
    8: 24.8,
    9: 24.8,
    10: 24.8,
    11: 24.8,
    12: 22.8,
    13: 22.8,
    14: 22.8,
    15: 22.8,
    16: 24.8,
    17: 24.8,
    18: 24.8,
    19: 24.8,
    20: 26.8,
    21: 26.8,
    22: 26.8,
    23: 26.8,
}
final_selling_rate_profile = {
    0: 27.1,
    1: 27.1,
    2: 27.1,
    3: 27.1,
    4: 27.1,
    5: 27.1,
    6: 27.1,
    7: 27.1,
    8: 25.1,
    9: 25.1,
    10: 25.1,
    11: 25.1,
    12: 23.1,
    13: 23.1,
    14: 23.1,
    15: 23.1,
    16: 25.1,
    17: 25.1,
    18: 25.1,
    19: 25.1,
    20: 27.1,
    21: 27.1,
    22: 27.1,
    23: 27.1,
}

final_buying_rate_profile_2 = {
    0: 26.5,
    10: 24.5,
    12: 22.5,
    14: 24.5,
    18: 26.5,
}
final_selling_rate_profile_2 = {
    0: 27.5,
    10: 25.5,
    12: 23.5,
    14: 25.5,
    18: 27.5,
}


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=6,
                                                                       hrs_of_day=list(
                                                                           range(12, 18)),
                                                                       final_buying_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1',
                         strategy=StorageStrategy(initial_soc=50,
                                                  final_buying_rate=final_buying_rate_profile,
                                                  final_selling_rate=final_selling_rate_profile,
                                                  max_abs_battery_power_kW=5.0),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage2',
                         strategy=StorageStrategy(initial_soc=50,
                                                  final_buying_rate=final_buying_rate_profile_2,
                                                  final_selling_rate=final_selling_rate_profile_2,
                                                  max_abs_battery_power_kW=5.0),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=4,
                                                                       hrs_of_day=list(
                                                                           range(12, 16)),
                                                                       final_buying_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H2 PV', strategy=PVStrategy(4),
                         appliance=PVAppliance()),

                ]
            ),
            Area('Cell Tower', strategy=CellTowerLoadHoursStrategy(avg_power_W=100,
                                                                   hrs_per_day=24,
                                                                   hrs_of_day=list(range(0, 24)),
                                                                   final_buying_rate=35),
                 appliance=SwitchableAppliance()),
        ],
        config=config
    )
    return area
