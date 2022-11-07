from typing import Dict, Union
from pathlib import Path
from pendulum import duration

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.influx_connection.connection import InfluxConnection
from gsy_framework.influx_connection.queries import InfluxQuery

from gsy_e.models.strategy.external_strategies.pv import PVUserProfileExternalStrategy
from gsy_e.models.strategy.external_strategies.load import LoadProfileExternalStrategy
from gsy_e.models.strategy.external_strategies.smart_meter import SmartMeterExternalStrategy


class InfluxCombinedExternalStrategy(SmartMeterExternalStrategy):
    # pylint: disable=too-many-arguments
    def __init__(
            self, query: InfluxQuery,
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


class InfluxLoadExternalStrategy(LoadProfileExternalStrategy):
    # pylint: disable=too-many-arguments
    def __init__(self, query: InfluxQuery,
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

        load_profile = query.exec()
        if(load_profile == False):
            raise ValueError("Query Result not usable as daily profile")

        super().__init__(daily_load_profile=load_profile,
                         fit_to_limit=fit_to_limit,
                         energy_rate_increase_per_update=energy_rate_increase_per_update,
                         update_interval=update_interval,
                         final_buying_rate=final_buying_rate,
                         initial_buying_rate=initial_buying_rate,
                         balancing_energy_ratio=balancing_energy_ratio,
                         use_market_maker_rate=use_market_maker_rate,
                         daily_load_profile_uuid=daily_load_profile_uuid)
    

class InfluxPVExternalStrategy(PVUserProfileExternalStrategy):
    # pylint: disable=too-many-arguments
    def __init__(
            self, query: InfluxQuery, panel_count: int = 1,
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
            raise ValueError("Query Result not usable as daily profile")

        super().__init__(power_profile=pv_profile,
                         panel_count=panel_count,
                         initial_selling_rate=initial_selling_rate,
                         final_selling_rate=final_selling_rate,
                         fit_to_limit=fit_to_limit,
                         update_interval=update_interval,
                         energy_rate_decrease_per_update=energy_rate_decrease_per_update,
                         use_market_maker_rate=use_market_maker_rate,
                         power_profile_uuid=power_profile_uuid)