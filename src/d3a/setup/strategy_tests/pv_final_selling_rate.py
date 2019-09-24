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
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy


def get_setup(config):
    from d3a_interface.constants_limits import ConstSettings
    ConstSettings.GeneralSettings.MAX_OFFER_TRAVERSAL_LENGTH = 1
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 Storage1', strategy=StorageStrategy(initial_soc=10,
                                                                 battery_capacity_kWh=15.0,
                                                                 initial_buying_rate=0,
                                                                 final_buying_rate=23.99,
                                                                 final_selling_rate=28.01),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage2', strategy=StorageStrategy(initial_soc=10,
                                                                 battery_capacity_kWh=15.0,
                                                                 initial_buying_rate=0,
                                                                 final_buying_rate=22.99,
                                                                 final_selling_rate=28.01),
                         appliance=SwitchableAppliance()),
                ],
                transfer_fee_pct=0,
            ),
            Area(
                'House 2',
                [

                    Area('H2 PV', strategy=PVStrategy(1, final_selling_rate=23.0),
                         appliance=PVAppliance()),

                ],
                transfer_fee_pct=0,
            ),
        ],
        config=config
    )
    return area
