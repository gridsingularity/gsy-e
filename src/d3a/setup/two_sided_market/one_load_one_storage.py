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
from d3a_interface.constants_limits import ConstSettings


def get_setup(config):
    # Two sided market
    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.LoadSettings.INITIAL_BUYING_RATE = 15
    ConstSettings.LoadSettings.FINAL_BUYING_RATE = 35

    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 Storage',
                         strategy=StorageStrategy(initial_capacity_kWh=0.6, risk=0),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 General Load', strategy=LoadHoursStrategy(
                        avg_power_W=100,
                        hrs_per_day=10,
                        hrs_of_day=list(range(8, 18)),
                        initial_buying_rate=ConstSettings.LoadSettings.INITIAL_BUYING_RATE,
                        final_buying_rate=ConstSettings.LoadSettings.FINAL_BUYING_RATE
                    ), appliance=SwitchableAppliance()),

                ]
            ),
        ],
        config=config
    )
    return area
