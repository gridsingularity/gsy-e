from gsy_framework.database_connection.connection import PostgreSQLConnection
from gsy_framework.database_connection.queries_base import QueryRaw
import json

connection_psql = PostgreSQLConnection("postgresql_fhaachen.cfg")

#qstring_t1 = 'SELECT version()'

#q_t1 = QueryRaw(connection_psql, qstring_t1, print)
#q_t1.exec()


qstring_t2 = 'SELECT time_bucket(\'15m\',datetime) AS "time", avg(value) AS "Erzeugung-PV" \
FROM eview WHERE datetime BETWEEN \'2022-08-14T22:00:00Z\' AND \'2022-08-15T22:00:00Z\' AND plant = \'FP-JUEL\' \
GROUP BY 1 ORDER BY 1'

print(qstring_t2)


def qrestype(qresults):
    dic = dict(qresults)


    dic = {k.strftime("%H:%M"):v for k,v in qresults}
    #dic = {k.isoformat():v for k,v in qresults}
    
    print(json.dumps(dic, indent = 4))
    

q_t2 = QueryRaw(connection_psql, qstring_t2, qrestype)
q_t2.exec()