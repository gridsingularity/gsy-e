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
from d3a_interface.constants_limits import ConstSettings


def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.GeneralSettings.EXPORT_OFFER_BID_TRADE_HR = True

    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [

                    Area('H1 Storage1', strategy=StorageStrategy(initial_soc=10,
                                                                 min_allowed_soc=10,
                                                                 battery_capacity_kWh=1.2,
                                                                 max_abs_battery_power_kW=5,
                                                                 initial_selling_rate=30,
                                                                 final_buying_rate=25,
                                                                 final_selling_rate=25.1,
                                                                 initial_buying_rate=0,
                                                                 fit_to_limit=True,
                                                                 update_interval=1),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage2', strategy=StorageStrategy(initial_soc=10,
                                                                 min_allowed_soc=10,
                                                                 battery_capacity_kWh=1.2,
                                                                 max_abs_battery_power_kW=5,
                                                                 initial_selling_rate=30,
                                                                 final_buying_rate=25,
                                                                 final_selling_rate=25.1,
                                                                 initial_buying_rate=0,
                                                                 fit_to_limit=True,
                                                                 update_interval=1),
                         appliance=SwitchableAppliance())
                ]
            ),

        ],
        config=config
    )
    return area
