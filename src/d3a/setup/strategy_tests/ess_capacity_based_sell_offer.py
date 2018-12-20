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
from d3a.models.strategy.load_hours import LoadHoursStrategy


'''
This setup file is being used to test a house with battery and a general load. StorageStrategy
puts its sell offer to the market based on its SOC i.e. lower the SOC higher would be the
sell offer rate.
'''


def get_setup(config):
    config.read_market_maker_rate(30)
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=24,
                                                                       hrs_of_day=list(
                                                                           range(0, 24)),
                                                                       final_buying_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(initial_capacity_kWh=6,
                                                                 battery_capacity_kWh=6,
                                                                 max_abs_battery_power_kW=6,
                                                                 break_even=(16.99, 17.01),
                                                                 cap_price_strategy=True),
                         appliance=SwitchableAppliance()),
                ]
            ),
        ],
        config=config
    )
    return area
