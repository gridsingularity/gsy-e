from gsy_e.models.area import Area
from gsy_e.gsy_e_core.util import d3a_path
import os

from gsy_e.models.strategy.predefined_load import DefinedLoadStrategy
from gsy_e.utils.influx_connection import InfluxConnection

class InfluxAreaFactory:
    def __init__(self, path_influx_config):
        self.ic = InfluxConnection(path_influx_config)

    def getArea(self, areaname):
        Area(
                areaname,
                [*[Area("House " + str(i), [
                    Area(f"H{i} General Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                  hrs_per_day=24,
                                                                  hrs_of_day=list(range(24))),
                    ),   
                ]) for i in range(1, 1000)]
                ]
            ),