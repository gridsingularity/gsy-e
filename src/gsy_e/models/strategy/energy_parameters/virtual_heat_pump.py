import logging
from typing import Optional, Union, Dict

import sympy as sp
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.utils import convert_W_to_kWh, convert_kWh_to_W
from pendulum import DateTime

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.energy_parameters.heat_pump import (
    HeatPumpEnergyParametersException, HeatPumpEnergyParametersBase, WATER_DENSITY,
    SPECIFIC_HEAT_CONST_WATER)
from gsy_e.models.strategy.profile import EnergyProfile

logger = logging.getLogger(__name__)

CALIBRATION_COEFFICIENT = 0.85
WATER_SPECIFIC_TEMPERATURE = 4182


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
            water_return_temp_C_profile_uuid: Optional[str] = None,
            dh_water_flow_m3_profile: Optional[Union[str, float, Dict]] = None,
            dh_water_flow_m3_profile_uuid: Optional[str] = None,
    ):
        super().__init__(
            maximum_power_rating_kW, min_temp_C, max_temp_C, initial_temp_C, tank_volume_l)

        self._water_supply_temp_C: [DateTime, float] = EnergyProfile(
            water_supply_temp_C_profile, water_supply_temp_C_profile_uuid,
            profile_type=InputProfileTypes.IDENTITY)

        self._water_return_temp_C: [DateTime, float] = EnergyProfile(
            water_return_temp_C_profile, water_return_temp_C_profile_uuid,
            profile_type=InputProfileTypes.IDENTITY)

        self._dh_water_flow_m3: [DateTime, float] = EnergyProfile(
            dh_water_flow_m3_profile, dh_water_flow_m3_profile_uuid,
            profile_type=InputProfileTypes.IDENTITY)

    def serialize(self):
        """Return dict with the current energy parameter values."""
        return {
            **super().serialize(),
            "water_supply_temp_C": self._water_supply_temp_C.input_profile,
            "water_supply_temp_C_uuid": self._water_supply_temp_C.input_profile_uuid,
            "water_return_temp_C": self._water_return_temp_C.input_profile,
            "water_return_temp_C_uuid": self._water_return_temp_C.input_profile_uuid,
            "dh_water_flow_m3_profile": self._dh_water_flow_m3.input_profile,
            "dh_water_flow_m3_profile_uuid": self._dh_water_flow_m3.input_profile_uuid,
        }

    def _rotate_profiles(self, current_time_slot: Optional[DateTime] = None):
        self._water_return_temp_C.read_or_rotate_profiles()
        self._water_supply_temp_C.read_or_rotate_profiles()
        self._dh_water_flow_m3.read_or_rotate_profiles()
        self.state.delete_past_state_values(current_time_slot)

    def _calc_energy_to_buy_maximum(self, time_slot: DateTime) -> float:
        pass

    def _calc_energy_to_buy_minimum(self, time_slot: DateTime) -> float:
        pass

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

    def _storage_temp_to_energy(self, storage_temp: float, time_slot: DateTime):
        if not self._min_temp_C < storage_temp < self._max_temp_C:
            logger.info(f"Storage temp {storage_temp} cannot exceed min ({self._min_temp_C}) / "
                        f"max ({self._max_temp_C}) tank temperatures.")
            storage_temp = max(min(storage_temp, self._max_temp_C), self._min_temp_C)

        dh_supply_temp = self._water_supply_temp_C.profile[time_slot]
        dh_return_temp = self._water_return_temp_C.profile[time_slot]
        current_storage_temp = self.state.get_storage_temp_C(time_slot)
        m_m3 = self._dh_water_flow_m3.profile[time_slot]
        m_kg_per_sec = m_m3 * 1000 / 3600
        q_out = m_kg_per_sec * WATER_SPECIFIC_TEMPERATURE * (dh_supply_temp - dh_return_temp)

        temp_differential_per_sec = (storage_temp - current_storage_temp) / GlobalConfig.slot_length.total_seconds()
        q_in = (WATER_DENSITY * WATER_SPECIFIC_TEMPERATURE *
                self._tank_volume_l * temp_differential_per_sec + q_out)
        condenser_temp = (q_in / (m_kg_per_sec * WATER_SPECIFIC_TEMPERATURE)) + storage_temp
        condenser_temp = min(condenser_temp, dh_supply_temp - 0.001)
        cop = CALIBRATION_COEFFICIENT * (dh_supply_temp / (dh_supply_temp - condenser_temp))
        p_el = q_in / cop
        energy_kWh = convert_W_to_kWh(p_el, GlobalConfig.slot_length)
        print(f"Calculated maximum electricity demand for heatpump. \n"
                    f"Target Storage Temperature: {storage_temp} C. \n"
                    f"Current Storage Temperature: {current_storage_temp} C. \n"
                    f"District Heating Supply Temperature: {dh_supply_temp} C. \n"
                    f"District Heating Return Temperature: {dh_return_temp} C. \n"
                    f"District Heating Water Flow: {m_m3} m3/hour. \n"
                    f"Temperature Differential: {temp_differential_per_sec} C/sec. \n"
                    f"Q Out: {q_out} W. Q In: {q_in} W. \n"
                    f"Condenser Temperature: {condenser_temp} C. COP: {cop}.\n"
                    f"Heatpump Power: {p_el} W.\n"
                    f"Heatpump Energy Consumption {energy_kWh} kWh.")
        return

    def _energy_to_storage_temp(self, energy_kWh: float, time_slot: DateTime) -> float:
        dh_supply_temp = self._water_supply_temp_C.profile[time_slot]
        dh_return_temp = self._water_return_temp_C.profile[time_slot]
        current_storage_temp = self.state.get_storage_temp_C(time_slot)
        m_m3 = self._dh_water_flow_m3.profile[time_slot]
        m_kg = m_m3 * 1000
        q_out = m_kg * WATER_SPECIFIC_TEMPERATURE * (dh_supply_temp - dh_return_temp)
        p_el = convert_kWh_to_W(energy_kWh, GlobalConfig.slot_length)

        q_in_sym, cop_sym, storage_temp_sym, temp_differential_sym, condenser_temp_sym = sp.symbols(
            "q_in, cop, storage_temp, temp_differential, condenser_temp")

        eq1 = sp.Eq(storage_temp_sym - current_storage_temp,
                    temp_differential_sym)
        eq2 = sp.Eq(WATER_DENSITY * WATER_SPECIFIC_TEMPERATURE *
                    self._tank_volume_l * temp_differential_sym + q_out,
                    q_in_sym)
        eq3 = sp.Eq((q_in_sym / (m_kg * WATER_SPECIFIC_TEMPERATURE)) + storage_temp_sym,
                    condenser_temp_sym)
        eq4 = sp.Eq(CALIBRATION_COEFFICIENT * (dh_supply_temp /
                                               (dh_supply_temp - condenser_temp_sym)),
                    cop_sym)
        eq5 = sp.Eq(q_in_sym / cop_sym,
                    p_el)
        ans = sp.solve(
            [eq1, eq2, eq3, eq4, eq5])

        for solution in ans:
            if solution.get(temp_differential_sym) < 0.0:
                continue
            storage_temp = solution.get(storage_temp_sym)
            q_in = solution.get(q_in_sym)
            cop = solution.get(cop_sym)
            condenser_temp = solution.get(condenser_temp_sym)
            temp_differential = solution.get(temp_differential_sym)
            print(f"Calculated maximum electricity demand for heatpump. \n"
                 f"Target Storage Temperature: {storage_temp} C. \n"
                 f"Current Storage Temperature: {current_storage_temp} C. \n"
                 f"District Heating Supply Temperature: {dh_supply_temp} C. \n"
                 f"District Heating Return Temperature: {dh_return_temp} C. \n"
                 f"District Heating Water Flow: {m_m3} m3. \n"
                 f"Temperature Differential: {temp_differential} C. \n"
                 f"Q Out: {q_out} J. Q In: {q_in} J. \n"
                 f"Condenser Temperature: {condenser_temp} C. COP: {cop}.\n"
                 f"Heatpump Power: {p_el} W")

            return storage_temp

    def event_traded_energy(self, time_slot: DateTime, energy_kWh: float):
        """React to an event_traded_energy."""
        super().event_traded_energy(time_slot, energy_kWh)
        self.state.update_energy_consumption_kWh(time_slot, energy_kWh)
