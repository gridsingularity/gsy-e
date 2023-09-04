from typing import Optional, Union, Dict
from gsy_e.models.strategy.energy_parameters.heat_pump import (
    HeatPumpEnergyParametersException, HeatPumpEnergyParametersBase)
from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_framework.constants_limits import ConstSettings
from pendulum import DateTime
from gsy_e.models.strategy.profile import EnergyProfile
from gsy_framework.read_user_profile import InputProfileTypes


class VirtualHeatpumpEnergyParameters(HeatPumpEnergyParametersBase):

    def __init__(
            self,
            maximum_power_rating_kW: float = ConstSettings.HeatPumpSettings.MAX_POWER_RATING_KW,
            min_temp_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C,
            max_temp_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C,
            initial_temp_C: float = ConstSettings.HeatPumpSettings.INIT_TEMP_C,
            tank_volume_l: float = ConstSettings.HeatPumpSettings.TANK_VOL_L,
            water_supply_temp_C_profile: Optional[Union[str, float, Dict]] = None,
            water_supply_temp_C_profile_uuid: Optional[str] = None,
            water_return_temp_C_profile: Optional[Union[str, float, Dict]] = None,
            water_return_temp_C_profile_profile_uuid: Optional[str] = None,
    ):
        super().__init__(
            maximum_power_rating_kW, min_temp_C, max_temp_C, initial_temp_C, tank_volume_l)

        self._water_supply_temp_C: [DateTime, float] = EnergyProfile(
            water_supply_temp_C_profile, water_supply_temp_C_profile_uuid,
            profile_type=InputProfileTypes.IDENTITY)

        self._water_return_temp_C: [DateTime, float] = EnergyProfile(
            water_return_temp_C_profile, water_return_temp_C_profile_profile_uuid,
            profile_type=InputProfileTypes.IDENTITY)

    def serialize(self):
        """Return dict with the current energy parameter values."""
        return {
            **super().serialize(),
            "water_supply_temp_C": self._water_supply_temp_C.input_profile,
            "water_supply_temp_C_uuid": self._water_supply_temp_C.input_profile_uuid,
            "water_return_temp_C": self._water_return_temp_C.input_profile,
            "water_return_temp_C_uuid": self._water_return_temp_C.input_profile_uuid,
        }

    def _rotate_profiles(self, current_time_slot: Optional[DateTime] = None):
        self._water_return_temp_C.read_or_rotate_profiles()
        self._water_supply_temp_C.read_or_rotate_profiles()
        super()._rotate_profiles(current_time_slot)

    def _calc_energy_to_buy_maximum(self, time_slot: DateTime) -> float:
        raise NotImplementedError

    def _calc_energy_to_buy_minimum(self, time_slot: DateTime) -> float:
        raise NotImplementedError

    def _calc_temp_decrease_K(self, time_slot: DateTime) -> float:
        temp_decrease_K = (
                self._water_supply_temp_C.profile[time_slot] -
                self._water_return_temp_C.profile[time_slot])
        if temp_decrease_K < -FLOATING_POINT_TOLERANCE:
            raise HeatPumpEnergyParametersException(
                f"Water supply temp ({self._water_supply_temp_C.profile[time_slot]} C) "
                f"should be greater than return temp "
                f"({self._water_return_temp_C.profile[time_slot]} C) on time slot {time_slot}.")
        return temp_decrease_K

    def _calc_temp_increase_K(self, time_slot: DateTime, energy_kWh: float) -> float:
        raise NotImplementedError

    def event_traded_energy(self, time_slot: DateTime, energy_kWh: float):
        """React to an event_traded_energy."""
        super().event_traded_energy(time_slot, energy_kWh)
        self.state.update_energy_consumption_kWh(time_slot, energy_kWh)
