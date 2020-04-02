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
from d3a.models.appliance.pv import PVAppliance
from d3a.models.area import Area
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.external_strategies.storage import StorageExternalStrategy
from d3a_interface.constants_limits import ConstSettings

ConstSettings.IAASettings.MARKET_TYPE = 2


def get_setup(config):
    print(f"external_redis_communicator: {config.external_redis_communicator}")
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('PV', strategy=PVStrategy(
                        max_panel_power_W=2000, initial_selling_rate=30, final_selling_rate=30.0),
                         appliance=PVAppliance()),
                    Area('storage', strategy=StorageExternalStrategy(
                        initial_soc=50, battery_capacity_kWh=20,
                        external_redis_communicator=config.external_redis_communicator),
                         appliance=SwitchableAppliance()),
                ],
            ),
        ],
        config=config
    )
    return area
