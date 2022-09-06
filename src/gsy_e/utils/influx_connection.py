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
            database=config['InfluxDB']['database']
        )
        self.db = database=config['InfluxDB']['database']
        self.tablename = config.get('Table','tablename',fallback='Strom')
        self.powerkey = config.get('Table','powerkey',fallback='P_ges')
    


    def getSmartmeterIDs(self):
        query = 'SHOW TAG VALUES ON "' + self.db + '" WITH KEY IN ("id")'
        query_res = list(self.client.query(query).get_points())

        def getValue(listitem):
            return listitem["value"]

        return list(map(getValue, query_res))



    def getAggregatedDataDict(self, interval = GlobalConfig.slot_length.in_minutes(),
                                    start = GlobalConfig.start_date,
                                    duration = GlobalConfig.sim_duration):

        query_res = self._influx_query(interval, start, duration)

        # sum smartmeters
        df = pd.concat(query_res.values(), axis=1)
        df = df.sum(axis=1).to_frame("W")

        # index renaming
        df.reset_index(level=0, inplace=True)
        df.rename({"index": "Interval"}, axis=1, inplace=True)

        # remove day from time data
        df["Interval"] = df["Interval"].map(lambda x: x.strftime("%H:%M"))

        # remove last row
        df.drop(df.tail(1).index, inplace=True)
        

        # convert to dictionary
        df.set_index("Interval", inplace=True)
        df_dict = df.to_dict().get("W")

        return df_dict

    def getData(self, interval = GlobalConfig.slot_length.in_minutes(),
                        start = GlobalConfig.start_date,
                        duration = GlobalConfig.sim_duration):

        query_res = self._influx_query(interval, start, duration)

        res_dict = dict()

        for k,v in query_res.items():
            #renaming
            v.reset_index(level=0, inplace=True)
            v.rename({"index": "Interval"}, axis=1, inplace=True)
            v.rename({"mean": "W"}, axis=1, inplace=True)

            # remove day from time data
            v["Interval"] = v["Interval"].map(lambda x: x.strftime("%H:%M"))

            # remove last row
            v.drop(v.tail(1).index, inplace=True)

            # convert to dictionary
            v.set_index("Interval", inplace=True)
            res_dict[k[1][0][1]] = v.to_dict().get("W")

        return res_dict

    
    def getDataPoint(self, sm_id, start = GlobalConfig.start_date, duration = GlobalConfig.slot_length):
        end = start + duration

        #query = 'SELECT mean("'+ self.powerkey +'") FROM "'+ self.tablename +'" WHERE time >= \'' + start.to_datetime_string() + '\' AND time <= \'' + end.to_datetime_string() + '\' AND id = \'' + str(sm_id) + '\''
        query = 'SELECT mean("'+ self.powerkey +'") FROM "'+ self.tablename +'" WHERE "id" = \'97\' AND time >= now() - 1d GROUP BY time(15m), "id" fill(linear)'
        return self.client.query(query)


    def _influx_query(self, interval, start, duration):
        end = start + duration

        query = 'SELECT mean("'+ self.powerkey +'") FROM "'+ self.tablename +'" WHERE time >= \'' + start.to_datetime_string() + '\' AND time <= \'' + end.to_datetime_string() + '\' GROUP BY time(' + str(interval) + 'm), "id" fill(linear)'

        return self.client.query(query)

    @staticmethod
    def to_csv(df, filepath):
        df.to_csv(filepath, sep=";", index=False) 