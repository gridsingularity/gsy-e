from gsy_e.utils.influx_area_factory import InfluxAreaFactory

factory = InfluxAreaFactory("influx_fhaachen.cfg", power_column="P_ges", tablename="Strom", keyname="id")

print(factory.getArea("FH Campus"))