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

WATER_SPECIFIC_HEAT_CAPACITY = 4182  # [J/kg°C]
GROUND_WATER_TEMPERATURE_C = 12


class HeatpumpStorageEnergySolver:
    # pylint: disable=too-many-instance-attributes,too-many-arguments
    """Solver that calculates heatpump storage temperature and energy."""
    def __init__(
            self, tank_volume_l: float, current_storage_temp_C: float, dh_supply_temp_C: float,
            dh_return_temp_C: float, dh_flow_m3_per_hour: float,
            target_storage_temp_C: Optional[float] = None, energy_kWh: Optional[float] = None,
            calibration_coefficient: float = ConstSettings.HeatPumpSettings.CALIBRATION_COEFFICIENT
    ):
        # Optional inputs
        self.energy_kWh = energy_kWh
        self.target_storage_temp_C = target_storage_temp_C
        # Inputs
        self.current_storage_temp_C = current_storage_temp_C
        self.dh_supply_temp_C = dh_supply_temp_C
        self.dh_return_temp_C = dh_return_temp_C
        self.dh_flow_kg_per_sec = dh_flow_m3_per_hour * 1000 / 3600
        if self.dh_flow_kg_per_sec < FLOATING_POINT_TOLERANCE:
            self.dh_flow_kg_per_sec = 0
        self._tank_volume_l = tank_volume_l
        # Outputs
        self.temp_differential_per_sec = None
        self.q_out_J = None
        self.q_in_J = None
        self.condenser_temp_C = None
        self.cop = None
        self.p_el_W = None
        self.calibration_coefficient = calibration_coefficient

    def __str__(self):
        return (
            "Calculated maximum electricity demand for heatpump. \n"
            f"Target Storage Temperature: {self.target_storage_temp_C} C. \n"
            f"Current Storage Temperature: {self.current_storage_temp_C} C. \n"
            f"District Heating Supply Temperature: {self.dh_supply_temp_C} C. \n"
            f"District Heating Return Temperature: {self.dh_return_temp_C} C. \n"
            f"District Heating Water Flow: {self.dh_flow_kg_per_sec} kg/sec. \n"
            f"Temperature Differential: {self.temp_differential_per_sec} C/sec. \n"
            f"Q Out: {self.q_out_J} W. Q In: {self.q_in_J} W. \n"
            f"Condenser Temperature: {self.condenser_temp_C} C. COP: {self.cop}.\n"
            f"Heatpump Power: {self.p_el_W} W.\n"
            f"Heatpump Energy Consumption {self.energy_kWh} kWh.")

    def _calculate_q_out(self):
        self.q_out_J = self.dh_flow_kg_per_sec * WATER_SPECIFIC_HEAT_CAPACITY * (
                self.dh_supply_temp_C - self.dh_return_temp_C)

    def calculate_energy_from_storage_temp(self):
        """Calculate energy based on target storage temp and other parameters."""
        assert self.target_storage_temp_C is not None
        self._calculate_q_out()

        self.temp_differential_per_sec = (
                (self.target_storage_temp_C - self.current_storage_temp_C) /
                GlobalConfig.slot_length.total_seconds())
        self.q_in_J = (WATER_DENSITY * WATER_SPECIFIC_HEAT_CAPACITY *
                       self._tank_volume_l * self.temp_differential_per_sec + self.q_out_J)
        if self.dh_flow_kg_per_sec < FLOATING_POINT_TOLERANCE:
            self.condenser_temp_C = 0.
            self.cop = 0.
            self.p_el_W = 0.
            self.energy_kWh = 0.
        else:
            self.condenser_temp_C = (self.q_in_J / (
                    self.dh_flow_kg_per_sec * WATER_SPECIFIC_HEAT_CAPACITY)
                              ) + self.target_storage_temp_C
            self.cop = self.calibration_coefficient * (
                    self.condenser_temp_C / (self.condenser_temp_C - GROUND_WATER_TEMPERATURE_C))
            self.p_el_W = self.q_in_J / self.cop
            self.energy_kWh = convert_W_to_kWh(self.p_el_W, GlobalConfig.slot_length)

    def calculate_storage_temp_from_energy(self):
        """Calculate target storage temp based on energy and other parameters."""
        assert self.energy_kWh is not None
        self._calculate_q_out()
        self.p_el_W = convert_kWh_to_W(self.energy_kWh, GlobalConfig.slot_length)

        (q_in_sym, cop_sym, storage_temp_sym,
         temp_differential_sym, condenser_temp_sym) = sp.symbols(
            "q_in, cop, storage_temp, temp_differential, condenser_temp")

        ans = sp.solve([
            sp.Eq((storage_temp_sym - self.current_storage_temp_C) /
                  GlobalConfig.slot_length.total_seconds(),
                  temp_differential_sym),
            sp.Eq(WATER_DENSITY * WATER_SPECIFIC_HEAT_CAPACITY *
                  self._tank_volume_l * temp_differential_sym + self.q_out_J,
                  q_in_sym),
            sp.Eq((q_in_sym / (
                    self.dh_flow_kg_per_sec * WATER_SPECIFIC_HEAT_CAPACITY)) + storage_temp_sym,
                  condenser_temp_sym),
            sp.Eq(self.calibration_coefficient * (
                    condenser_temp_sym / (condenser_temp_sym - GROUND_WATER_TEMPERATURE_C)),
                  cop_sym),
            sp.Eq(q_in_sym / cop_sym,
                  self.p_el_W)
        ])
        solution = max(ans, key=lambda result: result.get(temp_differential_sym))
        self.q_in_J = float(solution.get(q_in_sym))
        self.cop = float(solution.get(cop_sym))
        self.target_storage_temp_C = float(solution.get(storage_temp_sym))
        self.temp_differential_per_sec = float(solution.get(temp_differential_sym))
        self.condenser_temp_C = float(solution.get(condenser_temp_sym))


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
            calibration_coefficient: Optional[float] = None,
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

        self.calibration_coefficient = (
            calibration_coefficient
            if calibration_coefficient is not None
            else ConstSettings.HeatPumpSettings.CALIBRATION_COEFFICIENT
        )

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
        temp_decrease_C = temp_differential_per_sec * GlobalConfig.slot_length.total_seconds()
        new_temperature_without_operation_C = (
                self.state.get_storage_temp_C(time_slot) - temp_decrease_C)
        if new_temperature_without_operation_C < self._min_temp_C:
            temp_decrease_C = 0.0
            self._calculate_and_set_unmatched_demand(time_slot)
        assert temp_decrease_C <= 0.0
        return abs(temp_decrease_C)

    def _calculate_and_set_unmatched_demand(self, time_slot: DateTime):
        solver = HeatpumpStorageEnergySolver(
            tank_volume_l=self._tank_volume_l,
            current_storage_temp_C=self.state.get_storage_temp_C(time_slot),
            dh_supply_temp_C=self._water_supply_temp_C.profile[time_slot],
            dh_return_temp_C=self._water_return_temp_C.profile[time_slot],
            dh_flow_m3_per_hour=self._dh_water_flow_m3.profile[time_slot],
            target_storage_temp_C=self.state.get_storage_temp_C(time_slot),
            calibration_coefficient=self.calibration_coefficient)
        solver.calculate_energy_from_storage_temp()
        self.state.update_unmatched_demand_kWh(time_slot, solver.energy_kWh)

    def _calc_temp_increase_K(self, time_slot: DateTime, traded_energy_kWh: float) -> float:
        storage_temp = self._energy_to_target_storage_temp(traded_energy_kWh, time_slot)
        current_storage_temp = self.state.get_storage_temp_C(time_slot)
        return storage_temp - current_storage_temp + self.state.get_temp_decrease_K(time_slot)

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

        solver = HeatpumpStorageEnergySolver(
            tank_volume_l=self._tank_volume_l,
            current_storage_temp_C=self.state.get_storage_temp_C(time_slot),
            dh_supply_temp_C=self._water_supply_temp_C.profile[time_slot],
            dh_return_temp_C=self._water_return_temp_C.profile[time_slot],
            dh_flow_m3_per_hour=self._dh_water_flow_m3.profile[time_slot],
            target_storage_temp_C=target_storage_temp_C,
            calibration_coefficient=self.calibration_coefficient)
        solver.calculate_energy_from_storage_temp()

        logger.debug(solver)
        return solver.energy_kWh

    def _energy_to_target_storage_temp(
            self, energy_kWh: float, time_slot: DateTime) -> float:
        """
        Return the water storage temperature after the heatpump has consumed energy_kWh energy and
        produced heat with it.
         """
        # pylint: disable=too-many-locals
        solver = HeatpumpStorageEnergySolver(
            tank_volume_l=self._tank_volume_l,
            current_storage_temp_C=self.state.get_storage_temp_C(time_slot),
            dh_supply_temp_C=self._water_supply_temp_C.profile[time_slot],
            dh_return_temp_C=self._water_return_temp_C.profile[time_slot],
            dh_flow_m3_per_hour=self._dh_water_flow_m3.profile[time_slot],
            energy_kWh=energy_kWh,
            calibration_coefficient=self.calibration_coefficient)
        solver.calculate_storage_temp_from_energy()
        logger.debug(solver)

        return solver.target_storage_temp_C

    def event_traded_energy(self, time_slot: DateTime, energy_kWh: float):
        """React to an event_traded_energy."""
        self._decrement_posted_energy(time_slot, energy_kWh)
        self.state.update_energy_consumption_kWh(time_slot, energy_kWh)

    def _populate_state(self, time_slot: DateTime):
        last_time_slot = self.last_time_slot(time_slot)
        if last_time_slot in self._water_supply_temp_C.profile:
            # Update temp increase
            energy_kWh = self.state.get_energy_consumption_kWh(last_time_slot)
            if energy_kWh > FLOATING_POINT_TOLERANCE:
                self.state.update_temp_increase_K(
                    last_time_slot, self._calc_temp_increase_K(last_time_slot, energy_kWh))

            # Update last slot statistics (COP, heat demand, condenser temp)
            target_storage_temp_C = self.state.get_storage_temp_C(time_slot)
            solver = HeatpumpStorageEnergySolver(
                tank_volume_l=self._tank_volume_l,
                current_storage_temp_C=self.state.get_storage_temp_C(last_time_slot),
                dh_supply_temp_C=self._water_supply_temp_C.profile[last_time_slot],
                dh_return_temp_C=self._water_return_temp_C.profile[last_time_slot],
                dh_flow_m3_per_hour=self._dh_water_flow_m3.profile[last_time_slot],
                target_storage_temp_C=target_storage_temp_C,
                calibration_coefficient=self.calibration_coefficient)
            solver.calculate_energy_from_storage_temp()
            self.state.set_cop(last_time_slot, solver.cop)
            self.state.set_condenser_temp(last_time_slot, solver.condenser_temp_C)
            self.state.set_heat_demand(last_time_slot, solver.q_out_J)

        self.state.update_storage_temp(time_slot)

        self.state.set_temp_decrease_K(
            time_slot, self._calc_temp_decrease_K(time_slot))

        self._calc_energy_demand(time_slot)

    def event_market_cycle(self, current_time_slot):
        """To be called at the start of the market slot. """
        self._rotate_profiles(current_time_slot)
        self._populate_state(current_time_slot)
        supply_temp = self._water_supply_temp_C.profile[current_time_slot]
        return_temp = self._water_return_temp_C.profile[current_time_slot]
        assert supply_temp >= return_temp, f"Supply temperature {supply_temp} has to be greater " \
                                           f"than {return_temp}, timeslot {current_time_slot}"
