from gsy_framework.database_connection.connection import PostgreSQLConnection
from gsy_framework.database_connection.queries_base import QueryRaw
from gsy_framework.database_connection.queries_fhac import QueryFHACPV
from gsy_e.models.strategy.database import DatabasePVStrategy

import json
from datetime import date, datetime
from pendulum import duration, instance

connection_psql = PostgreSQLConnection("postgresql_fhaachen.cfg")

#qstring_t1 = 'SELECT version()'

#q_t1 = QueryRaw(connection_psql, qstring_t1, print)
#q_t1.exec()

sim_start = instance((datetime.combine(date(2022,8,14), datetime.min.time())))
sim_duration = duration(days=1)
sim_interval = 15
sim_end = sim_start + sim_duration

# qstring_t2 = 'SELECT time_bucket(\'15m\',datetime) AS "time", avg(value) AS "Erzeugung-PV" \
# FROM eview WHERE datetime BETWEEN \'2022-08-14T22:00:00Z\' AND \'2022-08-15T22:00:00Z\' AND plant = \'FP-JUEL\' \
# GROUP BY 1 ORDER BY 1'

qstring_t2 = f'SELECT time_bucket(\'15m\',datetime), avg(value) \
FROM eview WHERE datetime BETWEEN \'{sim_start.to_datetime_string()}\' AND \'{sim_end.to_datetime_string()}\' AND plant = \'FP-JUEL\' \
GROUP BY 1 ORDER BY 1'

def qrestype(qresults):
    dic = dict(qresults)


    dic = {k.strftime("%H:%M"):v*1000.0 for k,v in qresults}
    
    print(json.dumps(dic, indent = 4))
    

q_t2 = QueryRaw(connection_psql, qstring_t2, qrestype)
q_t2.exec()



query = QueryFHACPV(postgresConnection=connection_psql, plant="FP-JUEL", tablename="eview", start=sim_start)

#print(query.exec())

DatabasePVStrategy(query=query)