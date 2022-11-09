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
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.influx_connection.connection import InfluxConnection
from gsy_framework.influx_connection.queries_fhac import DataFHAachenAggregated
from gsy_framework.influx_connection.queries_pxl import DataQueryPXL
from gsy_framework.influx_connection.queries import DataQueryMQTT
from gsy_e.models.strategy.influx import InfluxLoadStrategy, InfluxPVStrategy, InfluxCombinedStrategy

def get_setup(config):
    ConstSettings.GeneralSettings.RUN_IN_REALTIME = True
    connection_pxl = InfluxConnection("influx_pxl.cfg")
    connection_fhaachen = InfluxConnection("influx_fhaachen.cfg")

    area = Area(
        "Grid",
        [
            Area(
                "PXL Campus",
                [
                    Area("main_P_L1", strategy=InfluxLoadStrategy(query = DataQueryPXL(connection_pxl, power_column="main_P_L1", tablename="Total_Electricity"))),
                    Area("main_P_L2", strategy=InfluxLoadStrategy(query = DataQueryPXL(connection_pxl, power_column="main_P_L2", tablename="Total_Electricity"))),
                    Area("main_P_L3", strategy=InfluxLoadStrategy(query = DataQueryPXL(connection_pxl, power_column="main_P_L3", tablename="Total_Electricity"))),
                    Area("PV_LS_105A_power", strategy=InfluxPVStrategy(query = DataQueryPXL(connection_pxl, power_column="PV_LS_105A_power", tablename="Total_Electricity"))),
                    Area("PV_LS_105B_power", strategy=InfluxPVStrategy(query = DataQueryPXL(connection_pxl, power_column="PV_LS_105B_power", tablename="Total_Electricity"))),
                    Area("PV_LS_105E_power", strategy=InfluxPVStrategy(query = DataQueryPXL(connection_pxl, power_column="PV_LS_105E_power", tablename="Total_Electricity"))),
                ]
            ),
            Area(
                "PXL Makerspace",
                [
                    Area("PXL_makerspace_EmbroideryMachine", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_EmbroideryMachine", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_LaserBig", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_LaserBig", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_LaserSmall", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_LaserSmall", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_MillingMachine", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_MillingMachine", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_Miscellaneous", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_Miscellaneous", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_PcLaserBig", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_PcLaserBig", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_PcLaserSmall", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_PcLaserSmall", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_PcUltimakers", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_PcUltimakers", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_PcVinylEmbroid", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_PcVinylEmbroid", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_PcbMilling", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_PcbMilling", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_Photostudio", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_Photostudio", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_Press", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_Press", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_SheetPress", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_SheetPress", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_Ultimaker3Left", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_Ultimaker3Left", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_Ultimaker3Right", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_Ultimaker3Right", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_UltimakerS5", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_UltimakerS5", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_VacuumFormer", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_VacuumFormer", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_VinylCutter", strategy=InfluxLoadStrategy(query = DataQueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_VinylCutter", tablename="mqtt_consumer"))),                
                ]
            ),
            Area(
                "FH Campus",
                [
                    Area("FH General Load", strategy=InfluxLoadStrategy(query = DataFHAachenAggregated(connection_fhaachen, power_column="P_ges", tablename="Strom"))),
                ]
            ),
            Area(
                "Berg",
                [
                    Area("Berg Business", strategy=InfluxCombinedStrategy(query = DataQueryMQTT(connection_pxl, power_column="Ptot", device="berg-business_main-distribution", tablename="smartpi", invert = True))),
                    Area("Berg House 1", strategy=InfluxCombinedStrategy(query = DataQueryMQTT(connection_pxl, power_column="Ptot", device="berg-house1_main-distribution", tablename="smartpi"))),
                    Area("Berg House 2", strategy=InfluxCombinedStrategy(query = DataQueryMQTT(connection_pxl, power_column="Ptot", device="berg-house2_main-distribution", tablename="smartpi"))),                                    
                ]
            ),
            Area("Commercial Energy Producer",
                 strategy=CommercialStrategy(energy_rate=30)
                 ),
        ],
        config=config
    )
    return area




# pip install -e .
# gsy-e run --setup bc4p -s 15m --enable-external-connection --start-date 2022-11-4