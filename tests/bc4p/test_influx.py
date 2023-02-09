from datetime import date, datetime
from pendulum import duration, instance

from gsy_framework.database_connection.connection import InfluxConnection
from gsy_framework.database_connection.queries_base import QueryRaw, Query
from gsy_framework.database_connection.queries_influx import QueryMQTT
from gsy_framework.database_connection.queries_fhac import QueryFHAC, QueryFHACAggregated
from gsy_framework.database_connection.queries_pxl import QueryPXL
from gsy_framework.database_connection.queries_eupen import QueryEupen
from gsy_e.utils.influx_area_factory import InfluxAreaFactory

config_fhaachen = "influx_fhaachen.cfg"
config_pxl = "influx_pxl.cfg"

connection1 = InfluxConnection(config_fhaachen);
connection2 = InfluxConnection(config_pxl);

#qstring = 'SHOW SERIES ON Energiedaten'
#rquery = QueryRaw(connection1, qstring)
#print(rquery.exec())

start_date = instance((datetime.combine(date(2022,7,27), datetime.min.time())))
sim_duration = duration(days=1)
sim_interval = 15

qstring1 = 'SHOW SERIES ON Energiedaten'
qstring2 = 'SHOW SERIES ON telegraf'
qstring3 = 'SHOW DATABASES'
qstring4 = 'SHOW MEASUREMENTS ON Energiedaten'
qstring5 = 'SHOW MEASUREMENTS ON telegraf'


qstring6 = 'SHOW FIELD KEYS ON Energiedaten FROM "Strom"'
qstring7 = 'SHOW FIELD KEYS ON telegraf FROM "Total_Electricity"'
qstring8 = 'SHOW FIELD KEYS ON telegraf FROM "shellies"'



qstring8 = 'SELECT mean("P_ges") FROM "Strom" WHERE time >= now() - 24h and time <= now() AND "id"=\'99\' GROUP BY time(15m) fill(null)'
qstring9 = 'SELECT mean("PV_LS_105A_power") FROM "Total_Electricity" WHERE time >= now() - 24h and time <= now() GROUP BY time(15m) fill(null)'
qstring10 = 'SELECT mean("P_ges") FROM "Strom" WHERE time >= "2022-10-09 00:00:00" and time <= "2022-10-10 00:00:00" GROUP BY time(15m), "id" fill(linear)'
qstring11 = 'SELECT mean("Power") FROM "mqtt_consumer" WHERE ("device" =~ /^PXL_makerspace_MillingMachine$/) AND time >= now() - 7d and time <= now() GROUP BY time(15m) fill(null)'
qstring11 = 'SELECT mean("Power") FROM "mqtt_consumer" WHERE "device" =~ /^PXL_makerspace_MillingMachine$/ AND time >= now() - 7d and time <= now() GROUP BY time(15m) fill(null)'
qstring12 = 'SELECT mean("Ptot") AS "Ptot" FROM "smartpi" WHERE ("device" =~ /^berg-business_main-distribution$/) AND time >= 1667522806364ms and time <= 1667609785798ms GROUP BY time(1m) fill(null)'



#eupenq = QueryEupen(connection2, location="Asten Johnson", power_column="W", key = "GridMs.TotW", tablename = "genossenschaft", start=start_date, duration=sim_duration, interval=sim_interval)
#print(eupenq.exec())


end = start_date + sim_duration
#print(start_date.to_datetime_string())
#print(end.to_datetime_string())
qstring13 = f'SELECT mean("W") FROM "genossenschaft" WHERE ("Location" = \'Asten Johnson\' AND "Key" = \'GridMs.TotW\') AND time >= \'{start_date.to_datetime_string()}\' AND time <= \'{end.to_datetime_string()}\' GROUP BY time(15m), "Meter" fill(null)'

def qrestype(qresults):
    print(qresults.values())

eupenq2 = QueryRaw(connection2, qstring13, qrestype)
eupenq2.exec()









#rquery1 = QueryRaw(connection1, qstring10, print)


#rquery2 = QueryRaw(connection2, qstring12, print)

#rquery1.exec()
#print("------------------------------------------------")
#rquery2.exec()


#fhquery = QueryFHAC(connection1, power_column="P_ges", tablename="Strom", smartmeterID="10", start=start_date, duration=sim_duration, interval=sim_interval)
#print(fhquery.exec())

#pxlquery = QueryPXL(connection2, power_column="main_P_L1", tablename="Total_Electricity", start=start_date, duration=sim_duration, interval=sim_interval)
#print(pxlquery.exec())


#pxlmakerquery = QueryMQTT(connection2, power_column="Power", device="PXL_makerspace_MillingMachine", tablename="mqtt_consumer", start=start_date, duration=sim_duration, interval=sim_interval)
#print(pxlmakerquery.exec())

#pxlmakerquery2 = QueryMQTT(connection2, power_column="Power", device="PXL_makerspace_EmbroideryMachine", tablename="mqtt_consumer")
#print(pxlmakerquery2.exec())

#bergquery = QueryMQTT(connection2, power_column="Ptot", device="berg-business_main-distribution", tablename="smartpi", start=start_date, duration=sim_duration, interval=sim_interval, multiplier = -1)
#print(bergquery.exec())

# squery = QuerySmartmeterID(connection, keyname="id")
# qres = squery.exec()
#print(qres)

# spquery = SingleDataPointQuery(connection, power_column="P_ges", tablename="Strom", smartmeterID="99")
# print(spquery.exec())

#factory = InfluxAreaFactory(path_fhaachen, power_column="P_ges", tablename="Strom", keyname="id")

#factory.getArea("FH Campus")

#dquery = QuerySingle(connection1, power_column="P_ges", tablename="Strom", keyname="id")
#dres = dquery.exec()
#print(dres)

# daquery = QueryAggregated(connection, power_column="P_ges", tablename="Strom", keyname="id")
# dares = daquery.exec()
#print(dares)


#agrquery = QueryFHACAggregated(connection1, power_column="P_ges", tablename="Strom", start=start_date, duration=sim_duration, interval=sim_interval)
#agrres = agrquery.exec()
#print(agrres)