
from gsy_framework.database_connection.connection import PostgreSQLConnection
from gsy_framework.database_connection.connection import InfluxConnection

connection_psql = PostgreSQLConnection("postgresql_fhaachen.cfg")
connection_psql.check()
connection_psql.close()

connection_fh = InfluxConnection("influx_fhaachen.cfg")
connection_fh.check()
connection_fh.close()

connection_pxl = InfluxConnection("influx_pxl.cfg")
connection_pxl.check()
connection_pxl.close()