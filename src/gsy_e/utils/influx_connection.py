import pandas as pd
import configparser

from influxdb import DataFrameClient

from gsy_framework.constants_limits import ConstSettings, GlobalConfig

class InfluxConnection:

    def __init__(self, path_influx_config):
        config = configparser.ConfigParser()
        config.read(path_influx_config)

        self.client = DataFrameClient(
            username=config['InfluxDB']['username'],
            password=config['InfluxDB']['password'],
            host=config['InfluxDB']['host'],
            path=config['InfluxDB']['path'],
            port=int(config['InfluxDB']['port']),
            ssl=True,
            verify_ssl=True,
            database=config['InfluxDB']['Database']
        )

    def getAggregatedDataDict(self, sim_interval=GlobalConfig.slot_length.in_minutes()):
        start = GlobalConfig.start_date
        end = GlobalConfig.start_date + GlobalConfig.sim_duration

        query = 'SELECT mean("P_ges") FROM "Strom" WHERE time >= \'' + start.to_datetime_string() + '\' AND time <= \'' + end.to_datetime_string() + '\' GROUP BY time(' + str(sim_interval) + 'm), "id" fill(linear)'

        # time >= now() - 24h and time <= now()

        result = self.client.query(query)

        df = pd.concat(result.values(), axis=1)
        df = df.sum(axis=1).to_frame("W")
        df = df.reset_index(level=0)
        df.rename({"index": "Interval"}, axis=1, inplace=True)

        # remove day from time data
        df["Interval"] = df["Interval"].map(lambda x: x.strftime("%H:%M"))

        # remove last row
        df.drop(df.tail(1).index,inplace=True)
        

        # convert to dictionary
        df.set_index("Interval", inplace=True)
        df_dict = df.to_dict().get("W")

        return df_dict


    @staticmethod
    def to_csv(df, filepath):
        df.to_csv(filepath, sep=";", index=False) 