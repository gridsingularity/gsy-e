#!/usr/bin/python3

from gsy_e.models.strategy.predefined_influx_load import DefinedLoadStrategyInflux

df = DefinedLoadStrategyInflux._getInfluxDBData("../setup/influxdb.cfg");
DefinedLoadStrategyInflux.to_csv(df, "FHCampus_InfluxDB.csv")