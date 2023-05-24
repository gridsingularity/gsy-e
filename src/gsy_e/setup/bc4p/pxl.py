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
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.database_connection.connection import InfluxConnection
from gsy_framework.database_connection.queries_pxl import QueryPXL
from gsy_e.models.strategy.database import DatabaseLoadStrategy, DatabasePVStrategy

def get_setup(config):
    connection_pxl = InfluxConnection("influx_pxl.cfg")

    area = Area(
        "Grid",
        [
            Area(
                "PXL Campus",
                [
                    Area("main_P_L1", strategy=DatabaseLoadStrategy(query = QueryPXL(connection_pxl, power_column="main_P_L1", tablename="Total_Electricity"))),
                    Area("main_P_L2", strategy=DatabaseLoadStrategy(query = QueryPXL(connection_pxl, power_column="main_P_L2", tablename="Total_Electricity"))),
                    Area("main_P_L3", strategy=DatabaseLoadStrategy(query = QueryPXL(connection_pxl, power_column="main_P_L3", tablename="Total_Electricity"))),
                    Area("PV_LS_105A_power", strategy=DatabasePVStrategy(query = QueryPXL(connection_pxl, power_column="PV_LS_105A_power", tablename="Total_Electricity", multiplier = 10.0))),
                    Area("PV_LS_105B_power", strategy=DatabasePVStrategy(query = QueryPXL(connection_pxl, power_column="PV_LS_105B_power", tablename="Total_Electricity", multiplier = 10.0))),
                    Area("PV_LS_105E_power", strategy=DatabasePVStrategy(query = QueryPXL(connection_pxl, power_column="PV_LS_105E_power", tablename="Total_Electricity", multiplier = 10.0))),
                ]
            ),

            Area("Market Maker", strategy=InfiniteBusStrategy(energy_buy_rate=10, energy_sell_rate=30)),
        ],
        config=config,
    )
    return area


# pip install -e .
# gsy-e run --setup bc4p.pxl -s 15m --enable-external-connection --start-date 2022-11-09