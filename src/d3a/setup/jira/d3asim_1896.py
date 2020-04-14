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
from d3a_interface.constants_limits import ConstSettings, RateRange
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.appliance.simple import SimpleAppliance


def get_setup(config):
    import d3a.constants
    d3a.constants.DISPATCH_EVENTS_BOTTOM_TO_TOP = True
    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 1
    ConstSettings.GeneralSettings.MIN_UPDATE_INTERVAL = 1
    ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE = 30
    ConstSettings.StorageSettings.SELLING_RATE_RANGE = RateRange(30, 15.1)
    ConstSettings.StorageSettings.BUYING_RATE_RANGE = RateRange(5, 15)

    area = Area(
        'Grid',
        [
            Area(
                'Microgrid',
                [
                    Area(
                        'House 1',
                        [
                            Area('H1 storage', strategy=StorageStrategy(
                                initial_soc=10,
                                battery_capacity_kWh=1,
                                max_abs_battery_power_kW=0.01,
                                initial_buying_rate=5,
                                final_buying_rate=15,
                                initial_selling_rate=30,
                                final_selling_rate=15.1,
                                update_interval=1
                            ), appliance=SwitchableAppliance())

                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                ],),
            Area('DSO', strategy=InfiniteBusStrategy(energy_sell_rate=15,
                                                     energy_buy_rate=0),
                 appliance=SimpleAppliance()),
        ],
        config=config
    )
    return area
