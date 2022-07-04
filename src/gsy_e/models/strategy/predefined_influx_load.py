import pandas as pd
import configparser
from influxdb import DataFrameClient
from typing import Union

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_e.models.strategy.predefined_load import DefinedLoadStrategy

class DefinedLoadStrategyInflux(DefinedLoadStrategy):
    """
        Strategy for creating a load profile. It accepts as an input a load csv file or a
        dictionary that contains the load values for each time point
    """
    # pylint: disable=too-many-arguments
    def __init__(self, path_influx_config,
                 fit_to_limit=True, energy_rate_increase_per_update=None,
                 update_interval=None,
                 initial_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.BUYING_RATE_RANGE.initial,
                 final_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.BUYING_RATE_RANGE.final,
                 balancing_energy_ratio: tuple =
                 (ConstSettings.BalancingSettings.OFFER_DEMAND_RATIO,
                  ConstSettings.BalancingSettings.OFFER_SUPPLY_RATIO),
                 use_market_maker_rate: bool = False,
                 daily_load_profile_uuid: str = None):
        """
        Constructor of DefinedLoadStrategy
        :param path_influx_config: path to config file with connection information of the Influx Database
        :param fit_to_limit: if set to True, it will make a linear curve
        following following initial_buying_rate & final_buying_rate
        :param energy_rate_increase_per_update: Slope of Load bids change per update
        :param update_interval: Interval after which Load will update its offer
        :param initial_buying_rate: Starting point of load's preferred buying rate
        :param final_buying_rate: Ending point of load's preferred buying rate
        :param balancing_energy_ratio: Portion of energy to be traded in balancing market
        :param use_market_maker_rate: If set to True, Load would track its final buying rate
        as per utility's trading rate
        """

        df = DefinedLoadStrategyInflux._getInfluxDBData(path_influx_config);
        
        super().__init__(daily_load_profile=df,
                         fit_to_limit=fit_to_limit,
                         energy_rate_increase_per_update=energy_rate_increase_per_update,
                         update_interval=update_interval,
                         final_buying_rate=final_buying_rate,
                         initial_buying_rate=initial_buying_rate,
                         balancing_energy_ratio=balancing_energy_ratio,
                         use_market_maker_rate=use_market_maker_rate,
                         daily_load_profile_uuid=daily_load_profile_uuid)

    @staticmethod
    def _createDataFrameClient(path_influx_config):
        config = configparser.ConfigParser()
        config.read(path_influx_config)

        client = DataFrameClient(
            username=config['InfluxDB']['username'],
            password=config['InfluxDB']['password'],
            host=config['InfluxDB']['host'],
            path=config['InfluxDB']['path'],
            port=int(config['InfluxDB']['port']),
            ssl=True,
            verify_ssl=True,
            database=config['InfluxDB']['Database']
        )
        return client

    @staticmethod
    def _getInfluxDBData(path_influx_config, sim_interval=GlobalConfig.slot_length.in_minutes()):
        client = DefinedLoadStrategyInflux._createDataFrameClient(path_influx_config)

        start = GlobalConfig.start_date
        end = GlobalConfig.start_date + GlobalConfig.sim_duration

        query = 'SELECT mean("P_ges") FROM "Strom" WHERE time >= \'' + start.to_datetime_string() + '\' AND time <= \'' + end.to_datetime_string() + '\' GROUP BY time(' + str(sim_interval) + 'm), "id" fill(linear)'

        # time >= now() - 24h and time <= now()

        result = client.query(query)

        df = pd.concat(result.values(), axis=1)
        df = df.sum(axis=1).to_frame("W")
        df = df.reset_index(level=0)
        df.rename({'index': 'Time'}, axis=1, inplace=True)

        # remove day from time data
        df["Time"] = pd.to_datetime(df['Time'], unit='ms').dt.time
        return df

    @staticmethod
    def to_csv(df, filepath):
        df.to_csv(filepath, sep=";", index=False) 