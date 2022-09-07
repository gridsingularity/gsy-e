import configparser

from influxdb import DataFrameClient

class InfluxConnection:
    def __init__(self, path_influx_config: str):
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
        self.db = config['InfluxDB']['database']

    def query(self, queryString: str):
        return self.client.query(queryString)

    def getDBName(self):
        return self.db

class InfluxQuery:
    def __init__(self, influxConnection: InfluxConnection):
        self.connection = influxConnection
    
    def set(self, querystring: str):
        self.qstring = querystring

    def exec(self):
        self.qresults = self.connection.query(self.qstring)
        return self._process()

    def _process(self):
        pass