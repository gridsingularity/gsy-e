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

from gsy_framework.constants_limits import ConstSettings

from gsy_e.models.area import Area
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.storage import StorageStrategy, StorageLosses


def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = 2
    area = Area(
        "Grid",
        children=[
            Area(
                "House 1",
                children=[
                    Area(
                        "General Load",
                        strategy=LoadHoursStrategy(
                            avg_power_W=500, hrs_of_day=list(range(0, 15)), final_buying_rate=30
                        ),
                    ),
                    Area(
                        "Storage with losses",
                        strategy=StorageStrategy(
                            losses=StorageLosses(
                                charging_loss_percent=0.05,
                                discharging_loss_percent=0.01,
                                self_discharge_per_day_percent=0.003,
                            ),
                            initial_soc=50,
                            battery_capacity_kWh=30,
                            max_abs_battery_power_kW=10,
                        ),
                    ),
                    Area("PV", strategy=PVStrategy(panel_count=4, capacity_kW=10)),
                ],
            ),
        ],
        config=config,
    )
    return area
