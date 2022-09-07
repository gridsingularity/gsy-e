from gsy_e.models.area import Area
from gsy_e.gsy_e_core.util import d3a_path
import os

from gsy_e.models.strategy.predefined_load import DefinedLoadStrategy
from gsy_e.utils.influx_connection import InfluxConnection
from gsy_e.utils.influx_queries import DataQuery

class InfluxAreaFactory:
    def __init__(self, path_influx_config, power_column, tablename, keyname):
        self.ic = InfluxConnection(path_influx_config)
        self.power_column = power_column
        self.tablename = tablename
        self.keyname = keyname


    def getArea(self, areaname):
        query = DataQuery(connection, power_column=self.power_column, tablename=self.tablename, keyname=self.keyname)
        qres = query.exec()

        res = Area(
            areaname,
            [
                *[Area(k, [
                    Area(k +" Load", strategy=DefinedLoadStrategy(
                             daily_load_profile=v,
                             final_buying_rate=35),
                    ),   
                ]) for k,v in qres.items()]
            ]
        )

        return res