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

import os

from gsy_framework.constants_limits import ConstSettings

from gsy_e.gsy_e_core.util import gsye_root_path
from gsy_e.models.area import Area
from gsy_e.models.strategy.heat_pump import PCMHeatPump
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy

ConstSettings.MASettings.MARKET_TYPE = 2
ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 5


def get_setup(config):
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area(
                        "PCM",
                        strategy=PCMHeatPump(
                            initial_temp_C=35,
                            max_temp_C=60,
                            min_temp_C=30,
                            maximum_power_rating_kW=6,
                            # preferred_buying_rate=12,
                            consumption_kWh_profile=os.path.join(
                                gsye_root_path, "resources", "hp_consumption_kWh.csv"
                            ),
                            source_temp_C_profile=os.path.join(
                                gsye_root_path, "resources", "hp_external_temp_C.csv"
                            ),
                        ),
                    ),
                ],
                grid_fee_percentage=0,
                grid_fee_constant=0,
            ),
            Area(
                "House 2",
                [
                    Area(
                        "H2 PV",
                        strategy=PVStrategy(
                            capacity_kW=20,
                            panel_count=1,
                            initial_selling_rate=24,
                            final_selling_rate=0,
                        ),
                    ),
                ],
                grid_fee_percentage=0,
                grid_fee_constant=0,
            ),
            Area(
                "Infinite Bus",
                strategy=InfiniteBusStrategy(energy_sell_rate=25, energy_buy_rate=0),
            ),
        ],
        config=config,
    )
    return area
