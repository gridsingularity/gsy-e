import logging
from typing import Optional, Union, Dict

import sympy as sp
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.utils import convert_W_to_kWh, convert_kWh_to_W
from pendulum import DateTime

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.energy_parameters.heat_pump import (
    HeatPumpEnergyParametersBase, WATER_DENSITY)
from gsy_e.models.strategy.profile import EnergyProfile

logger = logging.getLogger(__name__)

CALIBRATION_COEFFICIENT = 0.85
WATER_SPECIFIC_HEAT_CAPACITY = 4182  # [J/kg°C]
GROUND_WATER_TEMPERATURE_C = 12


class VirtualHeatpumpEnergyParameters(HeatPumpEnergyParametersBase):
    """Energy parameters for the virtual heatpump strategy class."""
    # pylint: disable=too-many-arguments
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
        max_energy_consumption = self._target_storage_temp_to_energy(self._max_temp_C, time_slot)
        assert max_energy_consumption > -FLOATING_POINT_TOLERANCE
        return min(self._max_energy_consumption_kWh, max_energy_consumption)

    def _calc_energy_to_buy_minimum(self, time_slot: DateTime) -> float:
        min_energy_consumption = self._target_storage_temp_to_energy(
            self.state.get_storage_temp_C(time_slot), time_slot)
        assert min_energy_consumption > -FLOATING_POINT_TOLERANCE
        return min(self._max_energy_consumption_kWh, min_energy_consumption)

    def _calc_temp_decrease_K(self, time_slot: DateTime) -> float:
        dh_supply_temp = self._water_supply_temp_C.profile[time_slot]
        dh_return_temp = self._water_return_temp_C.profile[time_slot]
        m_m3 = self._dh_water_flow_m3.profile[time_slot]
        m_kg_per_sec = m_m3 * 1000 / 3600
        q_out = m_kg_per_sec * WATER_SPECIFIC_HEAT_CAPACITY * (dh_supply_temp - dh_return_temp)
        temp_differential_per_sec = -q_out / (
                WATER_DENSITY * WATER_SPECIFIC_HEAT_CAPACITY * self._tank_volume_l)
        temp_decrease = temp_differential_per_sec * GlobalConfig.slot_length.total_seconds()
        assert temp_decrease <= 0.0
        return abs(temp_decrease)

    def _calc_temp_increase_K(self, time_slot: DateTime, traded_energy_kWh: float) -> float:
        storage_temp = self._energy_to_storage_temp(traded_energy_kWh, time_slot)
        current_storage_temp = self.state.get_storage_temp_C(time_slot)
        if storage_temp <= current_storage_temp:
            return 0
        return storage_temp - current_storage_temp

    def _target_storage_temp_to_energy(
            self, target_storage_temp_C: float, time_slot: DateTime) -> float:
        """
        Return the energy needed to be consumed by the heatpump in order to generate enough heat
        to warm the water tank to storage_temp degrees C.
         """
        if not self._min_temp_C < target_storage_temp_C < self._max_temp_C:
            logger.info(
                "Storage temp %s cannot exceed min (%s) / max (%s) tank temperatures.",
                target_storage_temp_C, self._min_temp_C, self._max_temp_C)
            target_storage_temp_C = max(
                min(target_storage_temp_C, self._max_temp_C), self._min_temp_C)

        m_m3 = self._dh_water_flow_m3.profile[time_slot]
        m_kg_per_sec = m_m3 * 1000 / 3600
        if m_kg_per_sec <= FLOATING_POINT_TOLERANCE:
            return 0.

        dh_supply_temp = self._water_supply_temp_C.profile[time_slot]
        dh_return_temp = self._water_return_temp_C.profile[time_slot]
        current_storage_temp = self.state.get_storage_temp_C(time_slot)
        q_out = m_kg_per_sec * WATER_SPECIFIC_HEAT_CAPACITY * (dh_supply_temp - dh_return_temp)

        temp_differential_per_sec = (
                (target_storage_temp_C - current_storage_temp) /
                GlobalConfig.slot_length.total_seconds())
        q_in = (WATER_DENSITY * WATER_SPECIFIC_HEAT_CAPACITY *
                self._tank_volume_l * temp_differential_per_sec + q_out)
        condenser_temp = (q_in /
                          (m_kg_per_sec * WATER_SPECIFIC_HEAT_CAPACITY)) + target_storage_temp_C
        cop = CALIBRATION_COEFFICIENT * (condenser_temp /
                                         (condenser_temp - GROUND_WATER_TEMPERATURE_C))
        p_el = q_in / cop
        energy_kWh = convert_W_to_kWh(p_el, GlobalConfig.slot_length)
        logger.debug("Calculated maximum electricity demand for heatpump. \n"
                     "Target Storage Temperature: %s C. \n"
                     "Current Storage Temperature: %s C. \n"
                     "District Heating Supply Temperature: %s C. \n"
                     "District Heating Return Temperature: %s C. \n"
                     "District Heating Water Flow: %s m3/hour. \n"
                     "Temperature Differential: %s C/sec. \n"
                     "Q Out: %s W. Q In: %s W. \n"
                     "Condenser Temperature: %s C. COP: %s.\n"
                     "Heatpump Power: %s W.\n"
                     "Heatpump Energy Consumption %s kWh.",
                     target_storage_temp_C, current_storage_temp, dh_supply_temp, dh_return_temp,
                     m_m3, temp_differential_per_sec, q_out, q_in, condenser_temp, cop, p_el,
                     energy_kWh)
        return energy_kWh

    def _energy_to_storage_temp(
            self, energy_kWh: float, time_slot: DateTime) -> float:
        """
        Return the water storage temperature after the heatpump has consumed energy_kWh energy and
        produced heat with it.
         """
        # pylint: disable=too-many-locals
        dh_supply_temp = self._water_supply_temp_C.profile[time_slot]
        dh_return_temp = self._water_return_temp_C.profile[time_slot]
        current_storage_temp = self.state.get_storage_temp_C(time_slot)
        m_m3 = self._dh_water_flow_m3.profile[time_slot]
        m_kg_per_sec = m_m3 * 1000 / 3600
        q_out = m_kg_per_sec * WATER_SPECIFIC_HEAT_CAPACITY * (dh_supply_temp - dh_return_temp)
        p_el = convert_kWh_to_W(energy_kWh, GlobalConfig.slot_length)

        (q_in_sym, cop_sym, storage_temp_sym,
         temp_differential_sym, condenser_temp_sym) = sp.symbols(
            "q_in, cop, storage_temp, temp_differential, condenser_temp")

        ans = sp.solve([
            sp.Eq((storage_temp_sym - current_storage_temp) /
                  GlobalConfig.slot_length.total_seconds(),
                  temp_differential_sym),
            sp.Eq(WATER_DENSITY * WATER_SPECIFIC_HEAT_CAPACITY *
                  self._tank_volume_l * temp_differential_sym + q_out,
                  q_in_sym),
            sp.Eq((q_in_sym / (m_kg_per_sec * WATER_SPECIFIC_HEAT_CAPACITY)) + storage_temp_sym,
                  condenser_temp_sym),
            sp.Eq(CALIBRATION_COEFFICIENT * (condenser_temp_sym /
                                             (condenser_temp_sym - GROUND_WATER_TEMPERATURE_C)),
                  cop_sym),
            sp.Eq(q_in_sym / cop_sym,
                  p_el)
        ])
        solution = max(ans, key=lambda result: result.get(temp_differential_sym))
        logger.debug(
            "Calculated maximum electricity demand for heatpump. \n"
            "Target Storage Temperature: %s C. \n"
            "Current Storage Temperature: %s C. \n"
            "District Heating Supply Temperature: %s C. \n"
            "District Heating Return Temperature: %s C. \n"
            "District Heating Water Flow: %s kg/sec. \n"
            "Temperature Differential: %s C. \n"
            "Q Out: %s J. Q In: %s J. \n"
            "Condenser Temperature: %s C. COP: %s.\n"
            "Heatpump Power: %s W",
            solution.get(storage_temp_sym), current_storage_temp, dh_supply_temp,
            dh_return_temp, m_kg_per_sec, solution.get(temp_differential_sym), q_out,
            solution.get(q_in_sym), solution.get(condenser_temp_sym), solution.get(cop_sym),
            p_el)

        return float(solution.get(storage_temp_sym))

    def event_traded_energy(self, time_slot: DateTime, energy_kWh: float):
        """React to an event_traded_energy."""
        super().event_traded_energy(time_slot, energy_kWh)
        self.state.update_energy_consumption_kWh(time_slot, energy_kWh)

    def event_market_cycle(self, current_time_slot):
        """To be called at the start of the market slot. """
        self._rotate_profiles(current_time_slot)
        self._populate_state(current_time_slot)
        supply_temp = self._water_supply_temp_C.profile[current_time_slot]
        return_temp = self._water_return_temp_C.profile[current_time_slot]
        assert supply_temp >= return_temp, f"Supply temperature {supply_temp} has to be greater " \
                                           f"than {return_temp}, timeslot {current_time_slot}"
