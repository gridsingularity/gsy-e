from gsy_e.models.area import Area
from gsy_e.gsy_e_core.util import d3a_path
import os

from gsy_e.utils.influx_connection import InfluxConnection
from gsy_e.models.strategy.influx import InfluxLoadStrategy
from gsy_e.utils.influx_queries import DataQueryFHAachen, SmartmeterIDQuery

class InfluxAreaFactory:
    def __init__(self, path_influx_config, power_column, tablename, keyname):
        self.ic = InfluxConnection(path_influx_config)
        self.power_column = power_column
        self.tablename = tablename
        self.keyname = keyname


    def _createSubArea(self, smartmeterID):
        query = 0;
        try:
            strat = InfluxLoadStrategy(query = DataQueryFHAachen(self.ic, power_column=self.power_column, tablename=self.tablename, smartmeterID=smartmeterID))

            res = Area(
                smartmeterID,
                [
                    Area(f"{smartmeterID} Load", strategy=strat),
                ]
            )
            return res
        except ValueError as err:
            return False




    def getArea(self, areaname):
        smquery = SmartmeterIDQuery(self.ic, self.keyname)
        idlist = smquery.exec()

        subarea_list = []

        for sm_id in idlist:
            subarea = self._createSubArea(str(sm_id))
            if(subarea != False):
                subarea_list.append(subarea)

        print(len(subarea_list))
        res = Area(
            areaname,
            [
                *[subarea for subarea in subarea_list]
            ]
        )

        return res