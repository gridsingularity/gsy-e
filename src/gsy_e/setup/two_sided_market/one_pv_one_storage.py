"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
from gsy_e.models.area import Area
from gsy_e.models.strategy.storage import StorageStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_framework.constants_limits import ConstSettings


def get_setup(config):
    # Two sided market
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.PVSettings.FINAL_SELLING_RATE = 0
    ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE = 30
    ConstSettings.StorageSettings.INITIAL_BUYING_RATE = 0
    ConstSettings.StorageSettings.FINAL_BUYING_RATE = 29.9
    ConstSettings.StorageSettings.INITIAL_SELLING_RATE = 30
    ConstSettings.StorageSettings.FINAL_SELLING_RATE = 30

    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 Storage",
                         strategy=StorageStrategy(initial_soc=50,
                                                  initial_selling_rate=30,
                                                  initial_buying_rate=0
                                                  )
                         ),
                ]
            ),
            Area(
                "House 2",
                [
                    Area("H2 PV",
                         strategy=PVStrategy(panel_count=4, capacity_kW=0.16)
                         ),

                ]
            ),
        ],
        config=config
    )
    return area
