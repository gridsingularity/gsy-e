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
from gsy_e.models.strategy.smart_meter import SmartMeterStrategy
from gsy_e.models.strategy.database import DatabaseLoadStrategy, DatabasePVStrategy, DatabaseCombinedStrategy
from gsy_framework.constants_limits import GlobalConfig
from gsy_e.utils.csv_to_dict import CsvToDict
from gsy_e.gsy_e_core.util import d3a_path

from datetime import date, datetime
from pendulum import duration, instance
import os

def get_setup(config):
    connection_pxl = InfluxConnection("influx_pxl.cfg")
    connection_fhaachen = InfluxConnection("influx_fhaachen.cfg")
    connection_psql = PostgreSQLConnection("postgresql_fhaachen.cfg")

    eupen_start_date = instance((datetime.combine(date(2022,7,27), datetime.min.time()))) 
    # liege_start_date = "2022-04-09"  
    liege_start_date = "2022-06-21"
    # liege_start_date = "2022-09-15"  

    area = Area(
        "Grid",
        [
            Area(
                "PXL Campus",
                [
                    Area("main_P_L1", strategy=DatabaseLoadStrategy(query = QueryPXL(connection_pxl, power_column="main_P_L1", tablename="Total_Electricity"))),
                    Area("main_P_L2", strategy=DatabaseLoadStrategy(query = QueryPXL(connection_pxl, power_column="main_P_L2", tablename="Total_Electricity"))),
                    Area("main_P_L3", strategy=DatabaseLoadStrategy(query = QueryPXL(connection_pxl, power_column="main_P_L3", tablename="Total_Electricity"))),
                    Area("PV_LS_105A_power", strategy=DatabasePVStrategy(query = QueryPXL(connection_pxl, power_column="PV_LS_105A_power", tablename="Total_Electricity"))),
                    Area("PV_LS_105B_power", strategy=DatabasePVStrategy(query = QueryPXL(connection_pxl, power_column="PV_LS_105B_power", tablename="Total_Electricity"))),
                    Area("PV_LS_105E_power", strategy=DatabasePVStrategy(query = QueryPXL(connection_pxl, power_column="PV_LS_105E_power", tablename="Total_Electricity"))),
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
                "FH Campus",
                [
                    Area("FH General Load", strategy=DatabaseLoadStrategy(query = QueryFHACAggregated(connection_fhaachen, power_column="P_ges", tablename="Strom"))),
                    Area("FH PV", strategy=DatabasePVStrategy(query = QueryFHACPV(postgresConnection=connection_psql, plant="FP-JUEL", tablename="eview"))),
                ]
            ),
            Area(
                "Berg",
                [
                    Area("Berg Business", strategy=DatabaseCombinedStrategy(query = QueryMQTT(connection_pxl, power_column="Ptot", device="berg-business_main-distribution", tablename="smartpi", multiplier = -1.0))),
                    Area("Berg House 1", strategy=DatabaseCombinedStrategy(query = QueryMQTT(connection_pxl, power_column="Ptot", device="berg-house1_main-distribution", tablename="smartpi"))),
                    Area("Berg House 2", strategy=DatabaseCombinedStrategy(query = QueryMQTT(connection_pxl, power_column="Ptot", device="berg-house2_main-distribution", tablename="smartpi"))),                                    
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
            Area(
                "Liege",
                [
                    Area("B04", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b04.csv"), multiplier=-1000.0))),
                    Area("B05a", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b05a.csv"), multiplier=-1000.0))),
                    Area("B06", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b06.csv"), multiplier=-1000.0))),
                    Area("B08", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b08.csv"), multiplier=-1000.0))),
                    Area("B09", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b09.csv"), multiplier=-1000.0))),
                    Area("B10", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b10.csv"), multiplier=-1000.0))),
                    Area("B11", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b11.csv"), multiplier=-1000.0))),
                    Area("B13", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b13.csv"), multiplier=-1000.0))),
                    Area("B15", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b15.csv"), multiplier=-1000.0))),
                    Area("B17", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b17.csv"), multiplier=-1000.0))),
                    Area("B21", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b21.csv"), multiplier=-1000.0))),
                    Area("B22", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b22.csv"), multiplier=-1000.0))),
                    Area("B23", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b23.csv"), multiplier=-1000.0))),
                    Area("B28", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b28.csv"), multiplier=-1000.0))),
                    Area("B31", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b31.csv"), multiplier=-1000.0))),
                    Area("B34", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b34.csv"), multiplier=-1000.0))),
                    Area("B36", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b36.csv"), multiplier=-1000.0))),
                    Area("B41", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b41.csv"), multiplier=-1000.0))),
                    Area("B42", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b42.csv"), multiplier=-1000.0))),
                    Area("B52", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b52.csv"), multiplier=-1000.0))),
                    Area("B529", strategy=SmartMeterStrategy(smart_meter_profile=CsvToDict.convert(path=os.path.join(d3a_path,"resources","liege",liege_start_date,"b529.csv"), multiplier=-1000.0))),
                ]
            ),
            Area("Market Maker", strategy=InfiniteBusStrategy(energy_buy_rate=10, energy_sell_rate=30)),
        ],
        config=config
    )
    return area




# pip install -e .
# gsy-e run --setup bc4p.demonstration -s 15m --start-date 2023-05-30