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
from d3a.d3a_core.device_registry import DeviceRegistry
from d3a.models.const import ConstSettings


device_registry_dict = {
    "H2 Storage": (42, 45),
    "H1 Load": (46, 47)
}


def get_setup(config):
    DeviceRegistry.REGISTRY = device_registry_dict
    ConstSettings.BalancingSettings.FLEXIBLE_LOADS_SUPPORT = False
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 Load', strategy=LoadHoursStrategy(
                        avg_power_W=50,
                        hrs_per_day=24,
                        hrs_of_day=list(range(0, 24)),
                    ), appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 Storage', strategy=StorageStrategy(initial_capacity_kWh=49.0,
                                                                battery_capacity_kWh=50.0),
                         appliance=SwitchableAppliance()),
                ]
            ),
        ],
        config=config
    )
    return area
