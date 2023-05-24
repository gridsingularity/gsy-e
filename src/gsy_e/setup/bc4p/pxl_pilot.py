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
from gsy_framework.database_connection.connection import InfluxConnection, PostgreSQLConnection
from gsy_framework.database_connection.queries_fhac import QueryFHACAggregated, QueryFHACPV
from gsy_framework.database_connection.queries_pxl import QueryPXL
from gsy_framework.database_connection.queries_influx import QueryMQTT
from gsy_framework.database_connection.queries_eupen import QueryEupen
from gsy_e.models.strategy.database import DatabaseLoadStrategy, DatabasePVStrategy, DatabaseCombinedStrategy
from gsy_framework.constants_limits import GlobalConfig

from datetime import date, datetime
from pendulum import duration, instance

def get_setup(config):
    connection_pxl = InfluxConnection("influx_pxl.cfg")
    connection_fhaachen = InfluxConnection("influx_fhaachen.cfg")
    connection_psql = PostgreSQLConnection("postgresql_fhaachen.cfg")

    eupen_start_date = instance((datetime.combine(date(2022,7,27), datetime.min.time())))

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
                    Area(
                        "PXL Makerspace",
                        [
                            Area("PXL_makerspace_EmbroideryMachine", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_EmbroideryMachine", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_LaserBig", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_LaserBig", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_LaserSmall", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_LaserSmall", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_MillingMachine", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_MillingMachine", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_Miscellaneous", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_Miscellaneous", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_PcLaserBig", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_PcLaserBig", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_PcLaserSmall", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_PcLaserSmall", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_PcUltimakers", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_PcUltimakers", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_PcVinylEmbroid", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_PcVinylEmbroid", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_PcbMilling", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_PcbMilling", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_Photostudio", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_Photostudio", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_Press", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_Press", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_SheetPress", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_SheetPress", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_Ultimaker3Left", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_Ultimaker3Left", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_Ultimaker3Right", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_Ultimaker3Right", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_UltimakerS5", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_UltimakerS5", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_VacuumFormer", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_VacuumFormer", tablename="mqtt_consumer"))),
                            Area("PXL_makerspace_VinylCutter", strategy=DatabaseLoadStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_VinylCutter", tablename="mqtt_consumer"))),                
                        ]
                    ),
                ]
            ),
            Area(
                "Eupen",
                [
                    Area("Asten Johnson", strategy=DatabasePVStrategy(query = QueryEupen(connection_pxl, location="Asten Johnson", power_column="W", key = "GridMs.TotW", tablename="genossenschaft", start=eupen_start_date))),
                    Area("Welkenraedt", strategy=DatabasePVStrategy(query = QueryEupen(connection_pxl, location="Welkenraedt", power_column="W", key= "GridMs.TotW", tablename="genossenschaft", start=eupen_start_date))),
                    Area("Ferme Miessen", strategy=DatabasePVStrategy(query = QueryEupen(connection_pxl, location="FermeMiessen", power_column="W", key= "GridMs.TotW", tablename="genossenschaft", start=eupen_start_date))),
                    Area("New Verlac", strategy=DatabasePVStrategy(query = QueryEupen(connection_pxl, location="NewVerlac", power_column="W", key= "GridMs.TotW", tablename="genossenschaft", start=eupen_start_date))),
                ]
            ),
            Area("Market Maker", strategy=InfiniteBusStrategy(energy_buy_rate=10, energy_sell_rate=30)),
        ],
        config=config,
        grid_fee_constant=3, 
    )
    return area




# pip install -e .
# gsy-e run --setup bc4p.pxl_pilot -s 15m --start-date 2023-05-05