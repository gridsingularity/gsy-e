
from gsy_framework.database_connection.connection import PostgreSQLConnection, InfluxConnection

connection_psql = PostgreSQLConnection("postgresql_fhaachen.cfg")
connection_psql.check()

connection_fh = InfluxConnection("influx_fhaachen.cfg")
connection_fh.check()

connection_pxl = InfluxConnection("influx_pxl.cfg")
connection_pxl.check()

connection_psql = PostgreSQLConnection("postgresql_city_aachen.cfg")
connection_psql.check()