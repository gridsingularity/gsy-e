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
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.gsy_e_core.device_registry import DeviceRegistry
from gsy_framework.constants_limits import ConstSettings


device_registry_dict = {
    "H1 Storage": (32, 35),
}


def get_setup(config):
    DeviceRegistry.REGISTRY = device_registry_dict
    ConstSettings.BalancingSettings.FLEXIBLE_LOADS_SUPPORT = False
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 Storage", strategy=StorageStrategy(initial_soc=12,
                                                                battery_capacity_kWh=50.0)
                         ),
                ]
            ),
            Area(
                "House 2",
                [
                    Area("H2 PV",
                         strategy=PVStrategy(capacity_kW=0.16,
                                             panel_count=4,
                                             initial_selling_rate=0)
                         ),

                ]
            ),
        ],
        config=config
    )
    return area
