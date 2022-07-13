from gsy_e.models.strategy.predefined_influx_load import DefinedLoadStrategyInflux

strat = DefinedLoadStrategyInflux("../src/gsy_e/resources/influxdb.cfg", final_buying_rate=35)