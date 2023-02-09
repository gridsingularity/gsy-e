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
from gsy_framework.database_connection.queries_fhac import QueryFHACAggregated
from gsy_framework.database_connection.queries_pxl import QueryPXL
from gsy_framework.database_connection.queries_influx import QueryMQTT
from gsy_e.models.strategy.external_strategies.database import DatabaseLoadExternalStrategy, DatabasePVExternalStrategy, DatabaseCombinedExternalStrategy

def get_setup(config):
    connection_pxl = InfluxConnection("influx_pxl.cfg")
    connection_fhaachen = InfluxConnection("influx_fhaachen.cfg")

    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 1
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE = 22

    area = Area(
        "Grid",
        [
            Area(
                "PXL Campus",
                [
                    Area("main_P_L1", strategy=DatabaseLoadExternalStrategy(query = QueryPXL(connection_pxl, power_column="main_P_L1", tablename="Total_Electricity"))),
                    Area("main_P_L2", strategy=DatabaseLoadExternalStrategy(query = QueryPXL(connection_pxl, power_column="main_P_L2", tablename="Total_Electricity"))),
                    Area("main_P_L3", strategy=DatabaseLoadExternalStrategy(query = QueryPXL(connection_pxl, power_column="main_P_L3", tablename="Total_Electricity"))),
                    Area("PV_LS_105A_power", strategy=DatabaseLoadExternalStrategy(query = QueryPXL(connection_pxl, power_column="PV_LS_105A_power", tablename="Total_Electricity"))),
                    Area("PV_LS_105B_power", strategy=DatabaseLoadExternalStrategy(query = QueryPXL(connection_pxl, power_column="PV_LS_105B_power", tablename="Total_Electricity"))),
                    Area("PV_LS_105E_power", strategy=DatabaseLoadExternalStrategy(query = QueryPXL(connection_pxl, power_column="PV_LS_105E_power", tablename="Total_Electricity"))),
                ], grid_fee_constant=0, external_connection_available=True
            ),
            Area(
                "PXL Makerspace",
                [
                    Area("PXL_makerspace_EmbroideryMachine", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_EmbroideryMachine", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_LaserBig", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_LaserBig", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_LaserSmall", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_LaserSmall", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_MillingMachine", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_MillingMachine", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_Miscellaneous", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_Miscellaneous", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_PcLaserBig", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_PcLaserBig", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_PcLaserSmall", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_PcLaserSmall", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_PcUltimakers", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_PcUltimakers", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_PcVinylEmbroid", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_PcVinylEmbroid", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_PcbMilling", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_PcbMilling", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_Photostudio", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_Photostudio", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_Press", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_Press", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_SheetPress", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_SheetPress", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_Ultimaker3Left", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_Ultimaker3Left", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_Ultimaker3Right", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_Ultimaker3Right", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_UltimakerS5", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_UltimakerS5", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_VacuumFormer", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_VacuumFormer", tablename="mqtt_consumer"))),
                    Area("PXL_makerspace_VinylCutter", strategy=DatabaseLoadExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Power", device="PXL_makerspace_VinylCutter", tablename="mqtt_consumer"))),                
                ], grid_fee_constant=0, external_connection_available=True
            ),
            Area(
                "FH Campus",
                [
                    Area("FH General Load", strategy=DatabaseLoadExternalStrategy(query = QueryFHACAggregated(connection_fhaachen, power_column="P_ges", tablename="Strom"))),
                ], grid_fee_constant=0, external_connection_available=True
            ),
            Area(
                "Berg",
                [
                    Area("Berg Business", strategy=DatabaseCombinedExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Ptot", device="berg-business_main-distribution", tablename="smartpi", multiplier = -1.0))),
                    Area("Berg House 1", strategy=DatabaseCombinedExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Ptot", device="berg-house1_main-distribution", tablename="smartpi"))),
                    Area("Berg House 2", strategy=DatabaseCombinedExternalStrategy(query = QueryMQTT(connection_pxl, power_column="Ptot", device="berg-house2_main-distribution", tablename="smartpi"))),                                    
                ], grid_fee_constant=0, external_connection_available=True
            ),
            Area("Market Maker", strategy=InfiniteBusStrategy(energy_buy_rate=21, energy_sell_rate=22)),
        ],
        config=config, 
        grid_fee_constant=1, 
        external_connection_available=True
    )
    return area




# pip install -e .
# gsy-e run --setup bc4p.assets.demonstration --enable-external-connection --start-date 2022-11-07 --paused