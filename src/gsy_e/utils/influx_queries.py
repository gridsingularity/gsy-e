from gsy_e.utils.influx_connection import InfluxConnection, InfluxQuery
from gsy_framework.constants_limits import GlobalConfig

import pandas as pd

class RawQuery(InfluxQuery):
    def __init__(self, influxConnection: InfluxConnection, querystring: str, procFunc):
        super().__init__(influxConnection)
        self.set(querystring)
        self.procFunc = procFunc

    def _process(self):
        return self.procFunc(self.qresults)


class SmartmeterIDQuery(InfluxQuery):
    def __init__(self, influxConnection: InfluxConnection, keyname: str):
        super().__init__(influxConnection)
        qstring = f'SHOW TAG VALUES ON "{self.connection.getDBName()}" WITH KEY IN ("{keyname}")'
        self.set(qstring)

    def _process(self):
        points = list(self.qresults.get_points())
        def getValue(listitem):
            return listitem["value"]
        return list(map(getValue, points))


class SingleDataPointQuery(InfluxQuery):
    def __init__(self, influxConnection: InfluxConnection,
                        power_column: str,
                        tablename: str,
                        smartmeterID: str,
                        slot_length = GlobalConfig.slot_length):
        super().__init__(influxConnection)

        qstring = f'SELECT mean("{power_column}") FROM "{tablename}" WHERE "id" = \'{smartmeterID}\' AND time >= now() - {slot_length.in_minutes()}m'
        self.set(qstring)
    
    def _process(self):
        value_list = list(self.qresults.values())[0]
        value_list.reset_index(level=0, inplace=True)
        return value_list["index"][0], value_list["mean"][0]



class DataQueryBase(InfluxQuery):
    def __init__(self, influxConnection: InfluxConnection,
                        power_column: str,
                        tablename: str,
                        keyname: str,
                        duration, start, interval):
        super().__init__(influxConnection)

        end = start + duration
        qstring = f'SELECT mean("{power_column}") FROM "{tablename}" WHERE time >= \'{start.to_datetime_string()}\' AND time <= \'{end.to_datetime_string()}\' GROUP BY time({interval}m), "{keyname}" fill(linear)'
        self.set(qstring)

    def _process(self):
        pass


class DataQuery(DataQueryBase):
    def __init__(self, influxConnection: InfluxConnection,
                        power_column: str,
                        tablename: str,
                        keyname: str,
                        duration = GlobalConfig.sim_duration,
                        start = GlobalConfig.start_date,
                        interval = GlobalConfig.slot_length.in_minutes()):
        super().__init__(influxConnection = influxConnection, power_column=power_column, tablename=tablename, keyname=keyname, duration=duration, start=start, interval=interval)

    def _process(self):
        res_dict = dict()
        for k,v in self.qresults.items():
            v.reset_index(level=0, inplace=True)

            # remove day from time data
            v["index"] = v["index"].map(lambda x: x.strftime("%H:%M"))

            # remove last row
            v.drop(v.tail(1).index, inplace=True)

            # convert to dictionary
            v.set_index("index", inplace=True)
            res_dict[k[1][0][1]] = v.to_dict().get("mean")

        return res_dict


class DataQueryFHAachen(InfluxQuery):
    def __init__(self, influxConnection: InfluxConnection,
                        power_column: str,
                        tablename: str,
                        smartmeterID: str,
                        duration = GlobalConfig.sim_duration,
                        start = GlobalConfig.start_date,
                        interval = GlobalConfig.slot_length.in_minutes()):
        super().__init__(influxConnection)

        end = start + duration
        qstring = f'SELECT mean("{power_column}") FROM "{tablename}" WHERE "id" = \'{smartmeterID}\' AND time >= \'{start.to_datetime_string()}\' AND time <= \'{end.to_datetime_string()}\' GROUP BY time({interval}m) fill(linear)'
        self.set(qstring)

    def _process(self):
        # Get DataFrame from result
        if(len(list(self.qresults.values())) != 1):
            return False;

        df = list(self.qresults.values())[0]

        df.reset_index(level=0, inplace=True)

        # remove day from time data
        df["index"] = df["index"].map(lambda x: x.strftime("%H:%M"))

        # remove last row
        df.drop(df.tail(1).index, inplace=True)

        # convert to dictionary
        df.set_index("index", inplace=True)
        ret = df.to_dict().get("mean")
        return ret


class DataAggregatedQuery(DataQueryBase):
    def __init__(self, influxConnection: InfluxConnection,
                        power_column: str,
                        tablename: str,
                        keyname: str,
                        duration = GlobalConfig.sim_duration,
                        start = GlobalConfig.start_date,
                        interval = GlobalConfig.slot_length.in_minutes()):
        super().__init__(influxConnection = influxConnection, power_column=power_column, tablename=tablename, keyname=keyname, duration=duration, start=start, interval=interval)

    def _process(self):
        # sum smartmeters
        df = pd.concat(self.qresults.values(), axis=1)
        df = df.sum(axis=1).to_frame("W")

        df.reset_index(level=0, inplace=True)

        # remove day from time data
        df["index"] = df["index"].map(lambda x: x.strftime("%H:%M"))

        # remove last row
        df.drop(df.tail(1).index, inplace=True)
        

        # convert to dictionary
        df.set_index("index", inplace=True)
        df_dict = df.to_dict().get("W")

        return df_dict