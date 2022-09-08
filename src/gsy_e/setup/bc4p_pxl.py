"""
Copyright 2022 BC4P
This file is part of BC4P.

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
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.storage import StorageStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_framework.constants_limits import ConstSettings
from gsy_e.models.strategy.predefined_influx_load import InfluxLoadStrategyAggregated
from gsy_e.models.strategy.predefined_pv import PVUserProfileStrategy
from gsy_e.gsy_e_core.util import d3a_path
import os

def get_setup(config):
    ConstSettings.GeneralSettings.RUN_IN_REALTIME = True
    area = Area(
        "Grid",
        [
            Area(
                "PXL Campus",
                [
                    Area("PV_LS_105A_power", strategy=InfluxLoadStrategyAggregated(os.path.join(d3a_path, "resources", "influxdb.cfg"), 
                                                                                power_column="PV_LS_105A_power",
                                                                                tablename="Total_Electricity",
                                                                                keyname="id",
                                                                                final_buying_rate=60)
                         ),
                ]
            ),

            Area("Commercial Energy Producer",
                 strategy=CommercialStrategy(energy_rate=30)
                 ),

            Area("Cell Tower", strategy=LoadHoursStrategy(avg_power_W=100,
                                                          hrs_per_day=24,
                                                          hrs_of_day=list(range(0, 24)))
                 )
        ],
        config=config
    )
    return area


PVUserProfileStrategy


SELECT mean("PV_LS_105A_power"), mean("PV_LS_105B_power"), mean("PV_LS_105E_power"), mean("main_P_L1"), mean("main_P_L2"), mean("main_P_L3"), mean("main_P_Total"), mean("main_kWh") AS "total" FROM "Total_Electricity" WHERE time >= now() - 24h and time <= now() GROUP BY time(1m) fill(null)