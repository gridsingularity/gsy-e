from typing import Dict, Union
from pathlib import Path
from pendulum import duration
from gsy_e.gsy_e_core.util import d3a_path
import os

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.database_connection.connection import InfluxConnection
from gsy_framework.database_connection.queries_base import Query

from gsy_e.models.strategy.predefined_load import DefinedLoadStrategy
from gsy_e.models.strategy.predefined_pv import PVUserProfileStrategy
from gsy_e.models.strategy.smart_meter import SmartMeterStrategy

class DatabaseCombinedStrategy(SmartMeterStrategy):
    """Class defining a strategy for Smart Meter devices."""
    # pylint: disable=too-many-arguments
    def __init__(
            self, query: Query,
            smart_meter_profile: Union[Path, str, Dict[int, float], Dict[str, float]] = None,
            initial_selling_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
            final_selling_rate: float = ConstSettings.SmartMeterSettings.SELLING_RATE_RANGE.final,
            energy_rate_decrease_per_update: Union[float, None] = None,
            initial_buying_rate: float = (
                ConstSettings.SmartMeterSettings.BUYING_RATE_RANGE.initial),
            final_buying_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
            energy_rate_increase_per_update: Union[float, None] = None,
            fit_to_limit: bool = True,
            update_interval=None,
            use_market_maker_rate: bool = False,
            smart_meter_profile_uuid: str = None):

        combined_strategy = query.exec()

        super().__init__(smart_meter_profile=combined_strategy,
                     initial_selling_rate=initial_selling_rate,
                     final_selling_rate=final_selling_rate,
                     energy_rate_decrease_per_update=energy_rate_decrease_per_update,
                     initial_buying_rate=initial_buying_rate,
                     final_buying_rate=final_buying_rate,
                     energy_rate_increase_per_update=energy_rate_increase_per_update,
                     fit_to_limit=fit_to_limit,
                     update_interval=update_interval,
                     use_market_maker_rate=use_market_maker_rate,
                     smart_meter_profile_uuid=smart_meter_profile_uuid)
                     
class DatabaseLoadStrategy(DefinedLoadStrategy):
    """
        Strategy for creating a load profile. It accepts as an input a load csv file or a
        dictionary that contains the load values for each time point
    """
    # pylint: disable=too-many-arguments
    def __init__(self, query: Query,
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
        self.query = query
        load_profile = query.exec()

        super().__init__(daily_load_profile=load_profile,
                         fit_to_limit=fit_to_limit,
                         energy_rate_increase_per_update=energy_rate_increase_per_update,
                         update_interval=update_interval,
                         final_buying_rate=final_buying_rate,
                         initial_buying_rate=initial_buying_rate,
                         balancing_energy_ratio=balancing_energy_ratio,
                         use_market_maker_rate=use_market_maker_rate,
                         daily_load_profile_uuid=daily_load_profile_uuid)

    def event_market_cycle(self):
        old_qstring = self.query.get_query_string()
        self.query.update_query(start = self.area.spot_market.time_slot._start_of_day()) 

        # if qstring changed, execute query again and reconfigure area
        if self.query.get_query_string() != old_qstring:
            self._energy_params._load_profile_input = self.query.exec()
            super().area_reconfigure_event(daily_load_profile=self._energy_params._load_profile_input)
        super().event_market_cycle()


class DatabasePVStrategy(PVUserProfileStrategy):  
    # pylint: disable=too-many-arguments
    def __init__(
            self, query: Query, panel_count: int = 1,
            initial_selling_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
            final_selling_rate: float = ConstSettings.PVSettings.SELLING_RATE_RANGE.final,
            fit_to_limit: bool = True,
            update_interval=duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL),
            energy_rate_decrease_per_update=None,
            use_market_maker_rate: bool = False,
            power_profile_uuid: str = None):

        pv_profile = query.exec()
        if(pv_profile == False):
            #raise ValueError("Query Result not usable as daily profile")
            print("PV Profile for Query:\n" + query.qstring + "\nnot valid. Using Zero Curve.")
            pv_profile = os.path.join(d3a_path, "resources", "Zero_Curve.csv")

        super().__init__(power_profile=pv_profile,
                         panel_count=panel_count,
                         initial_selling_rate=initial_selling_rate,
                         final_selling_rate=final_selling_rate,
                         fit_to_limit=fit_to_limit,
                         update_interval=update_interval,
                         energy_rate_decrease_per_update=energy_rate_decrease_per_update,
                         use_market_maker_rate=use_market_maker_rate,
                         power_profile_uuid=power_profile_uuid)