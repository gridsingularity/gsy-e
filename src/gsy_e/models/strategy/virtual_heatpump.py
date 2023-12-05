from typing import Optional, Union, Dict

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.validators.heat_pump_validator import VirtualHeatPumpValidator

from gsy_e.models.strategy.energy_parameters.virtual_heat_pump import (
    VirtualHeatpumpEnergyParameters)
from gsy_e.models.strategy.heat_pump import HeatPumpOrderUpdaterParameters, HeatPumpStrategy

VirtualHPSettings = ConstSettings.HeatPumpSettings


class VirtualHeatpumpStrategy(HeatPumpStrategy):
    # pylint: disable=super-init-not-called,too-many-arguments
    """
    Strategy that simulates a virtual heatpump, modelling how a home with an existing district
    heating network connection would work if there was a heatpump installed.
    """
    def __init__(
            self,
            maximum_power_rating_kW: float = VirtualHPSettings.MAX_POWER_RATING_KW,
            min_temp_C: float = VirtualHPSettings.MIN_TEMP_C,
            max_temp_C: float = VirtualHPSettings.MAX_TEMP_C,
            initial_temp_C: float = VirtualHPSettings.INIT_TEMP_C,
            tank_volume_l: float = VirtualHPSettings.TANK_VOL_L,
            water_supply_temp_C_profile: Optional[Union[str, float, Dict]] = None,
            water_supply_temp_C_profile_uuid: Optional[str] = None,
            water_return_temp_C_profile: Optional[Union[str, float, Dict]] = None,
            water_return_temp_C_profile_uuid: Optional[str] = None,
            dh_water_flow_m3_profile: Optional[Union[str, float, Dict]] = None,
            dh_water_flow_m3_profile_uuid: Optional[str] = None,
            order_updater_parameters: Dict[
                AvailableMarketTypes, HeatPumpOrderUpdaterParameters] = None,
            preferred_buying_rate: float = VirtualHPSettings.PREFERRED_BUYING_RATE):

        assert ConstSettings.MASettings.MARKET_TYPE != 1, (
                "Heatpump has not been implemented for the OneSidedMarket")

        self._init_price_params(order_updater_parameters, preferred_buying_rate)

        self._energy_params = VirtualHeatpumpEnergyParameters(
            maximum_power_rating_kW=maximum_power_rating_kW,
            min_temp_C=min_temp_C,
            max_temp_C=max_temp_C,
            initial_temp_C=initial_temp_C,
            tank_volume_l=tank_volume_l,
            water_supply_temp_C_profile=water_supply_temp_C_profile,
            water_supply_temp_C_profile_uuid=water_supply_temp_C_profile_uuid,
            water_return_temp_C_profile=water_return_temp_C_profile,
            water_return_temp_C_profile_uuid=water_return_temp_C_profile_uuid,
            dh_water_flow_m3_profile=dh_water_flow_m3_profile,
            dh_water_flow_m3_profile_uuid=dh_water_flow_m3_profile_uuid,
        )

        self.water_supply_temp_C_profile_uuid = water_supply_temp_C_profile_uuid
        self.water_return_temp_C_profile_uuid = water_return_temp_C_profile_uuid
        self.dh_water_flow_m3_profile_uuid = dh_water_flow_m3_profile_uuid

        VirtualHeatPumpValidator.validate(
            maximum_power_rating_kW=maximum_power_rating_kW,
            min_temp_C=min_temp_C,
            max_temp_C=max_temp_C,
            initial_temp_C=initial_temp_C,
            tank_volume_l=tank_volume_l,
            water_supply_temp_C_profile=water_supply_temp_C_profile,
            water_supply_temp_C_profile_uuid=water_supply_temp_C_profile_uuid,
            water_return_temp_C_profile=water_return_temp_C_profile,
            water_return_temp_C_profile_uuid=water_return_temp_C_profile_uuid,
            dh_water_flow_m3_profile=dh_water_flow_m3_profile,
            dh_water_flow_m3_profile_uuid=dh_water_flow_m3_profile_uuid,
        )
