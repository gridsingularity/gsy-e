from gsy_e.gsy_e_core.util import d3a_path
import os
from datetime import date, datetime
from pendulum import duration, instance

from gsy_e.utils.influx_connection import InfluxConnection, InfluxQuery
from gsy_e.utils.influx_queries import SmartmeterIDQuery, SingleDataPointQuery, RawQuery, DataQueryFHAachen, DataQueryPXL
from gsy_e.utils.influx_area_factory import InfluxAreaFactory
from gsy_e.models.strategy.influx import InfluxLoadStrategy, InfluxPVStrategy

path_fhaachen = os.path.join(d3a_path, "resources", "influx_fhaachen.cfg")
path_pxl = os.path.join(d3a_path, "resources", "influx_pxl.cfg")
# strat = InfluxLoadStrategyAggregated(path_fhaachen, final_buying_rate=60, power_column="P_ges", tablename="Strom", keyname="id")

connection1 = InfluxConnection(path_fhaachen);
connection2 = InfluxConnection(path_pxl);

#qstring = 'SHOW SERIES ON Energiedaten'
#rquery = RawQuery(connection1, qstring)
#print(rquery.exec())

start_date = instance((datetime.combine(date(2022,9,8), datetime.min.time())))
sim_duration = duration(days=1)
sim_interval = 15

qstring1 = 'SHOW SERIES ON Energiedaten'
qstring2 = 'SHOW SERIES ON telegraf'
qstring3 = 'SHOW DATABASES'
qstring4 = 'SHOW MEASUREMENTS ON Energiedaten'
qstring5 = 'SHOW MEASUREMENTS ON telegraf'


qstring6 = 'SHOW FIELD KEYS ON Energiedaten FROM "Strom"'
qstring7 = 'SHOW FIELD KEYS ON telegraf FROM "Total_Electricity"'

qstring8 = 'SELECT mean("P_ges") FROM "Strom" WHERE time >= now() - 24h and time <= now() AND "id"=\'99\' GROUP BY time(15m) fill(null)'
qstring9 = 'SELECT mean("PV_LS_105A_power") FROM "Total_Electricity" WHERE time >= now() - 24h and time <= now() GROUP BY time(15m) fill(null)'
qstring10 = 'SELECT mean("P_ges") FROM "Strom" WHERE time >= now() - 24h and time <= now() AND "id" = \'1\' GROUP BY time(15m) fill(linear)'

rquery1 = RawQuery(connection1, qstring1, print)
rquery2 = RawQuery(connection2, qstring9, print)

#rquery1.exec()
#print("------------------------------------------------")
rquery2.exec()


fhquery = DataQueryFHAachen(connection1, power_column="P_ges", tablename="Strom", smartmeterID="10")
#print(fhquery.exec())

pxlquery = DataQueryPXL(connection2, power_column="main_P_L1", tablename="Total_Electricity", start=start_date, duration=sim_duration, interval=sim_interval)
#print(pxlquery.exec())


pvquery = DataQueryPXL(connection2, power_column="PV_LS_105A_power", tablename="Total_Electricity", start=start_date, duration=sim_duration, interval=sim_interval)
print(pvquery.exec())


# squery = SmartmeterIDQuery(connection, keyname="id")
# qres = squery.exec()
#print(qres)

# spquery = SingleDataPointQuery(connection, power_column="P_ges", tablename="Strom", smartmeterID="99")
# print(spquery.exec())

#factory = InfluxAreaFactory(path_fhaachen, power_column="P_ges", tablename="Strom", keyname="id")

#factory.getArea("FH Campus")

#dquery = DataQuery(connection1, power_column="P_ges", tablename="Strom", keyname="id")
#dres = dquery.exec()
#print(dres)

# daquery = DataAggregatedQuery(connection, power_column="P_ges", tablename="Strom", keyname="id")
# dares = daquery.exec()
#print(dares)