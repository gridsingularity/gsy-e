from gsy_e.gsy_e_core.util import d3a_path
import os

from gsy_e.utils.influx_connection import InfluxConnection, InfluxQuery
from gsy_e.utils.influx_queries import SmartmeterIDQuery, SingleDataPointQuery, DataQuery, DataAggregatedQuery
from gsy_e.utils.influx_area_factory import InfluxAreaFactory
from gsy_e.models.strategy.predefined_influx_load import InfluxLoadStrategyAggregated

influx_path = os.path.join(d3a_path, "resources", "influxdb.cfg")
strat = InfluxLoadStrategyAggregated(influx_path, final_buying_rate=60, power_column="P_ges", tablename="Strom", keyname="id")

connection = InfluxConnection(influx_path);

squery = SmartmeterIDQuery(connection, keyname="id")
qres = squery.exec()
#print(qres)

spquery = SingleDataPointQuery(connection, power_column="P_ges", tablename="Strom", smartmeterID="99")
#print(spquery.exec())

factory = InfluxAreaFactory(influx_path, power_column="P_ges", tablename="Strom", keyname="id")

print(factory.getArea("FH Campus"))

dquery = DataQuery(connection, power_column="P_ges", tablename="Strom", keyname="id")
dres = dquery.exec()
#print(dres)

daquery = DataAggregatedQuery(connection, power_column="P_ges", tablename="Strom", keyname="id")
dares = daquery.exec()
#print(dares)