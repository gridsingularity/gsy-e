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
from d3a.models.const import ConstSettings
from d3a.d3a_core.device_registry import DeviceRegistry


device_registry_dict = {
    "H1 Storage": (32, 35),
    "H2 General Load": (32, 35),
}


def get_setup(config):
    DeviceRegistry.REGISTRY = device_registry_dict
    ConstSettings.BalancingSettings.FLEXIBLE_LOADS_SUPPORT = False
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
    # Two sided market
    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.LoadSettings.INITIAL_BUYING_RATE = 0
    ConstSettings.LoadSettings.FINAL_BUYING_RATE = 35

    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 Storage',
                         strategy=StorageStrategy(initial_capacity_kWh=10,
                                                  battery_capacity_kWh=12,
                                                  risk=0),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 General Load', strategy=LoadHoursStrategy(
                        avg_power_W=100,
                        hrs_per_day=24,
                        hrs_of_day=list(range(0, 24)),
                        initial_buying_rate=ConstSettings.LoadSettings.INITIAL_BUYING_RATE,
                        final_buying_rate=ConstSettings.LoadSettings.FINAL_BUYING_RATE
                    ), appliance=SwitchableAppliance()),

                ]
            ),
        ],
        config=config
    )
    return area
