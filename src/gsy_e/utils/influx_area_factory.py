from gsy_e.models.area import Area
from gsy_e.gsy_e_core.util import d3a_path
import os

from gsy_e.models.strategy.predefined_load import DefinedLoadStrategy
from gsy_e.utils.influx_connection import InfluxConnection

class InfluxAreaFactory:
    def __init__(self, path_influx_config):
        self.ic = InfluxConnection(path_influx_config)

    def getArea(self, areaname):

        influx_data = self.ic.getData()

        res = Area(
            areaname,
            [
                *[Area(k, [
                    Area(k +"General Load", strategy=DefinedLoadStrategy(
                             daily_load_profile=v,
                             final_buying_rate=35),
                    ),   
                ]) for k,v in influx_data.items()]
            ]
        )

        return res