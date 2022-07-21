from gsy_e.gsy_e_core.util import d3a_path
import os

from gsy_e.utils.influx_connection import InfluxConnection
from gsy_e.models.strategy.predefined_influx_load import DefinedLoadStrategyInflux

strat = DefinedLoadStrategyInflux(os.path.join(d3a_path, "resources", "influxdb.cfg"), final_buying_rate=60)
connection = InfluxConnection(os.path.join(d3a_path, "resources", "influxdb.cfg"));
print(connection.getAggregatedDataDict())

