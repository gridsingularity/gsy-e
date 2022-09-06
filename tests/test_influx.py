from gsy_e.gsy_e_core.util import d3a_path
import os

from gsy_e.utils.influx_connection import InfluxConnection
from gsy_e.utils.influx_area_factory import InfluxAreaFactory
from gsy_e.models.strategy.predefined_influx_load import DefinedLoadStrategyInflux

influx_path = os.path.join(d3a_path, "resources", "influxdb.cfg")
#strat = DefinedLoadStrategyInflux(influx_path, final_buying_rate=60)
connection = InfluxConnection(influx_path);

#print(connection.getAggregatedDataDict())

#factory = InfluxAreaFactory(influx_path)

#print(factory.getArea("FH Campus"))


#print(connection.getData())


print(connection.getDataPoint(99))