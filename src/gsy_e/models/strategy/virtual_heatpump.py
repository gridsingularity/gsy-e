from typing import Optional, Union, Dict

from pendulum import DateTime

from gsy_framework.constants_limits import ConstSettings
from gsy_e.models.strategy.energy_parameters.virtual_heat_pump import (
    VirtualHeatpumpEnergyParameters)

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import Trade, TraderDetails
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.validators.heat_pump_validator import HeatPumpValidator
from pendulum import DateTime, duration
from gsy_e.models.strategy.heat_pump import HeatPumpOrderUpdaterParameters, HeatPumpStrategy


class VirtualHeatpumpStrategy(HeatPumpStrategy):

    def __init__(
            self, order_updater_parameters,
            maximum_power_rating_kW: float =
            ConstSettings.HeatPumpSettings.MAX_POWER_RATING_KW,
            min_temp_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C,
            max_temp_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C,
            initial_temp_C: float = ConstSettings.HeatPumpSettings.INIT_TEMP_C,
            external_temp_C_profile: Optional[Union[str, float, Dict]] = None,
            external_temp_C_profile_uuid: Optional[str] = None,
            tank_volume_l: float = ConstSettings.HeatPumpSettings.TANK_VOL_L,
                 ):
        self.use_default_updater_params: bool = not order_updater_parameters
        if self.use_default_updater_params:
            order_updater_parameters = {
                AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters()}
        else:
            for market_type in AvailableMarketTypes:
                if not order_updater_parameters.get(market_type):
                    continue
                HeatPumpValidator.validate_rate(
                    initial_buying_rate=order_updater_parameters[market_type].initial_rate,
                    final_buying_rate=order_updater_parameters[market_type].final_rate,
                    update_interval=order_updater_parameters[market_type].update_interval,
                    preferred_buying_rate=preferred_buying_rate
                )

        super().__init__(order_updater_parameters=order_updater_parameters)

        self._energy_params = VirtualHeatPumpEnergyParameters(
            maximum_power_rating_kW=maximum_power_rating_kW,
            min_temp_C=min_temp_C,
            max_temp_C=max_temp_C,
            initial_temp_C=initial_temp_C,
            external_temp_C_profile=external_temp_C_profile,
            external_temp_C_profile_uuid=external_temp_C_profile_uuid,
            tank_volume_l=tank_volume_l,
            consumption_kWh_profile=consumption_kWh_profile,
            consumption_kWh_profile_uuid=consumption_kWh_profile_uuid,
            source_type=source_type
        )
        HeatPumpValidator.validate(
            maximum_power_rating_kW=maximum_power_rating_kW,
            min_temp_C=min_temp_C,
            max_temp_C=max_temp_C,
            initial_temp_C=initial_temp_C,
            external_temp_C_profile=external_temp_C_profile,
            external_temp_C_profile_uuid=external_temp_C_profile_uuid,
            tank_volume_l=tank_volume_l,
            consumption_kWh_profile=consumption_kWh_profile,
            consumption_kWh_profile_uuid=consumption_kWh_profile_uuid,
            source_type=source_type)

        self.preferred_buying_rate = preferred_buying_rate

        # needed for profile_handler
        self.external_temp_C_profile_uuid = external_temp_C_profile_uuid
        self.consumption_kWh_profile_uuid = consumption_kWh_profile_uuid

    def _get_energy_buy_energy(self, buy_rate: float, market_slot: DateTime) -> float:
        pass
