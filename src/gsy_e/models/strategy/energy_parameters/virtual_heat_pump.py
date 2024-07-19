from dataclasses import dataclass
import logging
from typing import Optional, Union, Dict, List

import sympy as sp
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.utils import convert_W_to_kWh, convert_kWh_to_W
from pendulum import DateTime

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.energy_parameters.heat_pump import (
    HeatPumpEnergyParametersBase,
    TankParameters,
    AllTanksEnergyParameters,
)
from gsy_e.models.strategy.energy_parameters.heat_pump_tank import (
    WATER_SPECIFIC_HEAT_CAPACITY,
    WATER_DENSITY,
)
from gsy_e.models.strategy.state.heat_pump_state import HeatPumpTankState
from gsy_e.models.strategy.strategy_profile import StrategyProfile

logger = logging.getLogger(__name__)

GROUND_WATER_TEMPERATURE_C = 12


@dataclass
class TankSolverParameters:
    tank_volume_L: float
    current_storage_temp_C: float
    target_storage_temp_C: float = None
    temp_differential_per_sec: Optional[float] = None

    def __str__(self):
        return (
            f"Tank Volume: {self.tank_volume_L} Current Temp: {self.current_storage_temp_C}"
            f"Target Temp: {self.target_storage_temp_C} "
            f"Temp Differential: {self.temp_differential_per_sec}"
        )


class HeatpumpStorageEnergySolver:
    # pylint: disable=too-many-instance-attributes,too-many-arguments
    """Solver that calculates heatpump storage temperature and energy."""

    def __init__(
        self,
        dh_supply_temp_C: float,
        dh_return_temp_C: float,
        dh_flow_m3_per_hour: float,
        tank_parameters: List[TankSolverParameters],
        energy_kWh: Optional[float] = None,
        calibration_coefficient: float = ConstSettings.HeatPumpSettings.CALIBRATION_COEFFICIENT,
    ):
        # Optional inputs
        self.energy_kWh = energy_kWh
        # Inputs
        self.tank_parameters = tank_parameters
        self.dh_supply_temp_C = dh_supply_temp_C
        self.dh_return_temp_C = dh_return_temp_C
        self.dh_flow_kg_per_sec = dh_flow_m3_per_hour * 1000 / 3600
        if self.dh_flow_kg_per_sec < FLOATING_POINT_TOLERANCE:
            self.dh_flow_kg_per_sec = 0
        # Outputs
        self.q_out_J = None
        self.q_in_J = None
        self.condenser_temp_C = None
        self.cop = None
        self.p_el_W = None
        self.calibration_coefficient = calibration_coefficient

    def __str__(self):
        return (
            "Calculated maximum electricity demand for heatpump. \n"
            f"Tank Parameters: [{self.tank_parameters}]"
            f"District Heating Supply Temperature: {self.dh_supply_temp_C} C. \n"
            f"District Heating Return Temperature: {self.dh_return_temp_C} C. \n"
            f"District Heating Water Flow: {self.dh_flow_kg_per_sec} kg/sec. \n"
            f"Q Out: {self.q_out_J} W. Q In: {self.q_in_J} W. \n"
            f"Condenser Temperature: {self.condenser_temp_C} C. COP: {self.cop}.\n"
            f"Heatpump Power: {self.p_el_W} W.\n"
            f"Heatpump Energy Consumption {self.energy_kWh} kWh."
        )

    def _calculate_q_out(self):
        self.q_out_J = (
            self.dh_flow_kg_per_sec
            * WATER_SPECIFIC_HEAT_CAPACITY
            * (self.dh_supply_temp_C - self.dh_return_temp_C)
        )

    def calculate_energy_from_storage_temp(self):
        """Calculate energy based on target storage temp and other parameters."""
        assert all(tank.target_storage_temp_C is not None for tank in self.tank_parameters)
        self._calculate_q_out()

        # Aggregated energy required in order to dictate how much energy will be needed from the
        # heatpump for all tanks to reach their target storage temperature.
        tanks_temp_increase_energy_J = 0
        for tank in self.tank_parameters:
            # Calculate the temp differential for a single tank
            tank.temp_differential_per_sec = (
                tank.target_storage_temp_C - tank.current_storage_temp_C
            ) / GlobalConfig.slot_length.total_seconds()

            tanks_temp_increase_energy_J += (
                WATER_DENSITY
                * WATER_SPECIFIC_HEAT_CAPACITY
                * tank.tank_volume_L
                * tank.temp_differential_per_sec
            )

        self.q_in_J = tanks_temp_increase_energy_J + self.q_out_J
        if self.dh_flow_kg_per_sec < FLOATING_POINT_TOLERANCE:
            self.condenser_temp_C = 0.0
            self.cop = 0.0
            self.p_el_W = 0.0
            self.energy_kWh = 0.0
        else:
            # Qin = mC(Tcond-Ttarget), therefore for multiple tanks with the same coefficients,
            # the equation expands to:
            # Qin = mC(Tcond-Ttarget1) + mC(Tcond-Ttarget2) + ...
            # Solving by Tcond:
            # Tcond = ((Qin / mC) + Ttarget1 + Ttarget2 + .... ) / nr_tanks
            self.condenser_temp_C = (
                self.q_in_J / (self.dh_flow_kg_per_sec * WATER_SPECIFIC_HEAT_CAPACITY)
            ) + sum(tank.target_storage_temp_C for tank in self.tank_parameters) / len(
                self.tank_parameters
            )
            self.cop = self.calibration_coefficient * (
                self.condenser_temp_C / (self.condenser_temp_C - GROUND_WATER_TEMPERATURE_C)
            )
            self.p_el_W = self.q_in_J / self.cop
            self.energy_kWh = convert_W_to_kWh(self.p_el_W, GlobalConfig.slot_length)

    def calculate_storage_temp_from_energy(self):
        """Calculate target storage temp based on energy and other parameters."""
        assert self.energy_kWh is not None
        self._calculate_q_out()
        self.p_el_W = convert_kWh_to_W(self.energy_kWh, GlobalConfig.slot_length)

        sympy_symbols_string = "q_in, cop, condenser_temp"
        for tank_index, _ in enumerate(self.tank_parameters):
            sympy_symbols_string += f", storage_temp_{tank_index}, temp_differential_{tank_index}"

        sp_symbols = sp.symbols(sympy_symbols_string)
        q_in_sym = sp_symbols[0]
        cop_sym = sp_symbols[1]
        condenser_temp_sym = sp_symbols[2]
        tank_symbols = sp_symbols[3:]

        equation_list = [
            sp.Eq(
                (tank_symbols[2 * tank_index] - tank.current_storage_temp_C)
                / GlobalConfig.slot_length.total_seconds(),
                tank_symbols[2 * tank_index + 1],
            )
            for tank_index, tank in enumerate(self.tank_parameters)
        ]
        sum_of_tanks_target_temp_expr = sp.Add(
            *[tank_symbols[2 * tank_index] for tank_index, _ in enumerate(self.tank_parameters)]
        )

        sum_of_tanks_heat_demand_expr = sp.Add(
            *[
                (
                    WATER_DENSITY
                    * WATER_SPECIFIC_HEAT_CAPACITY
                    * tank.tank_volume_L
                    * tank_symbols[2 * tank_index]
                    + 1
                )
                for tank_index, tank in enumerate(self.tank_parameters)
            ]
        )

        ans = sp.solve(
            [
                *equation_list,
                sp.Eq(sum_of_tanks_heat_demand_expr + self.q_out_J, q_in_sym),
                sp.Eq(
                    (
                        (q_in_sym / (self.dh_flow_kg_per_sec * WATER_SPECIFIC_HEAT_CAPACITY))
                        + sum_of_tanks_target_temp_expr
                    )
                    / len(self.tank_parameters),
                    condenser_temp_sym,
                ),
                sp.Eq(
                    self.calibration_coefficient
                    * (condenser_temp_sym / (condenser_temp_sym - GROUND_WATER_TEMPERATURE_C)),
                    cop_sym,
                ),
                sp.Eq(q_in_sym / cop_sym, self.p_el_W),
            ]
        )
        solution = max(ans, key=lambda result: result.get(tank_symbols[1]))
        self.q_in_J = float(solution.get(q_in_sym))
        self.cop = float(solution.get(cop_sym))
        for tank_index, tank in enumerate(self.tank_parameters):
            tank.target_storage_temp_C = float(solution.get(tank_symbols[2 * tank_index]))
            tank.temp_differential_per_sec = float(solution.get(tank_symbols[2 * tank_index] + 1))
        self.condenser_temp_C = float(solution.get(condenser_temp_sym))


class VirtualHeatpumpEnergyParameters(HeatPumpEnergyParametersBase):
    """Energy parameters for the virtual heatpump strategy class."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        maximum_power_rating_kW: float = ConstSettings.HeatPumpSettings.MAX_POWER_RATING_KW,
        tank_parameters: List[TankParameters] = None,
        water_supply_temp_C_profile: Optional[Union[str, float, Dict]] = None,
        water_supply_temp_C_profile_uuid: Optional[str] = None,
        water_return_temp_C_profile: Optional[Union[str, float, Dict]] = None,
        water_return_temp_C_profile_uuid: Optional[str] = None,
        dh_water_flow_m3_profile: Optional[Union[str, float, Dict]] = None,
        dh_water_flow_m3_profile_uuid: Optional[str] = None,
        calibration_coefficient: Optional[float] = None,
    ):
        super().__init__(maximum_power_rating_kW=maximum_power_rating_kW)
        if not tank_parameters:
            tank_parameters = [TankParameters()]

        self._tanks = AllTanksEnergyParameters(tank_parameters)

        self._water_supply_temp_C: [DateTime, float] = StrategyProfile(
            water_supply_temp_C_profile,
            water_supply_temp_C_profile_uuid,
            profile_type=InputProfileTypes.IDENTITY,
        )

        self._water_return_temp_C: [DateTime, float] = StrategyProfile(
            water_return_temp_C_profile,
            water_return_temp_C_profile_uuid,
            profile_type=InputProfileTypes.IDENTITY,
        )

        self._dh_water_flow_m3: [DateTime, float] = StrategyProfile(
            dh_water_flow_m3_profile,
            dh_water_flow_m3_profile_uuid,
            profile_type=InputProfileTypes.IDENTITY,
        )

        self.calibration_coefficient = (
            calibration_coefficient
            if calibration_coefficient is not None
            else ConstSettings.HeatPumpSettings.CALIBRATION_COEFFICIENT
        )

    def serialize(self):
        """Return dict with the current energy parameter values."""
        return {
            **self._tanks.serialize(),
            "max_energy_consumption_kWh": self._max_energy_consumption_kWh,
            "maximum_power_rating_kW": self._maximum_power_rating_kW,
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
        max_energy_consumption = self._max_storage_temp_to_energy(time_slot)
        assert max_energy_consumption > -FLOATING_POINT_TOLERANCE
        return min(self._max_energy_consumption_kWh, max_energy_consumption)

    def _calc_energy_to_buy_minimum(self, time_slot: DateTime) -> float:
        min_energy_consumption = self._current_storage_temp_to_energy(time_slot)
        assert min_energy_consumption > -FLOATING_POINT_TOLERANCE
        return min(self._max_energy_consumption_kWh, min_energy_consumption)

    def _set_temp_decrease_per_tank(
        self,
        tank: TankParameters,
        tank_state: HeatPumpTankState,
        time_slot: DateTime,
        q_out: float,
    ):
        temp_differential_per_sec = -q_out / (
            WATER_DENSITY * WATER_SPECIFIC_HEAT_CAPACITY * tank.tank_volume_L
        )
        temp_decrease_C = temp_differential_per_sec * GlobalConfig.slot_length.total_seconds()
        new_temperature_without_operation_C = (
            tank_state.get_storage_temp_C(time_slot) - temp_decrease_C
        )
        if new_temperature_without_operation_C < tank.min_temp_C:
            temp_decrease_C = 0.0
            self._calculate_and_set_unmatched_demand(time_slot)
        assert temp_decrease_C <= 0.0
        tank_state.set_temp_decrease_K(time_slot, abs(temp_decrease_C))

    def _set_temp_decrease_for_all_tanks(self, time_slot: DateTime):
        dh_supply_temp = self._water_supply_temp_C.get_value(time_slot)
        dh_return_temp = self._water_return_temp_C.get_value(time_slot)
        m_m3 = self._dh_water_flow_m3.get_value(time_slot)
        m_kg_per_sec = m_m3 * 1000 / 3600
        q_out = m_kg_per_sec * WATER_SPECIFIC_HEAT_CAPACITY * (dh_supply_temp - dh_return_temp)

        self._tanks.set_temp_decrease()
        for tank_index, tank in enumerate(self._tank_parameters):
            self._set_temp_decrease_per_tank(tank, self._tanks_state[tank_index], time_slot, q_out)

    def _calculate_and_set_unmatched_demand(self, time_slot: DateTime):
        energy_kWh = self._current_storage_temp_to_energy(time_slot)
        self.state.update_unmatched_demand_kWh(time_slot, energy_kWh)

    def _calc_temp_increase_K(self, time_slot: DateTime, traded_energy_kWh: float) -> float:
        storage_temp = self._energy_to_target_storage_temp(traded_energy_kWh, time_slot)
        current_storage_temp = self.state.get_storage_temp_C(time_slot)
        return storage_temp - current_storage_temp + self.state.get_temp_decrease_K(time_slot)

    def _current_storage_temp_to_energy(self, time_slot: DateTime) -> float:
        """
        Return the energy needed to be consumed by the heatpump in order to generate enough heat
        to warm the water tank to storage_temp degrees C.
        """
        tank_parameters = []
        for tank_index, tank in enumerate(self._tank_parameters):
            current_storage_temp_C = self._tanks_state[tank_index].get_storage_temp_C(time_slot)
            target_storage_temp_C = current_storage_temp_C
            if not tank.min_temp_C < target_storage_temp_C < tank.max_temp_C:
                logger.info(
                    "Storage temp %s cannot exceed min (%s) / max (%s) tank temperatures.",
                    target_storage_temp_C,
                    tank.min_temp_C,
                    tank.max_temp_C,
                )
                target_storage_temp_C = max(
                    min(target_storage_temp_C, tank.max_temp_C), tank.min_temp_C
                )
            tank_parameters.append(
                TankSolverParameters(
                    tank_volume_L=tank.tank_volume_L,
                    current_storage_temp_C=current_storage_temp_C,
                    target_storage_temp_C=target_storage_temp_C,
                )
            )

        solver = HeatpumpStorageEnergySolver(
            tank_parameters=tank_parameters,
            dh_supply_temp_C=self._water_supply_temp_C.get_value(time_slot),
            dh_return_temp_C=self._water_return_temp_C.get_value(time_slot),
            dh_flow_m3_per_hour=self._dh_water_flow_m3.get_value(time_slot),
            calibration_coefficient=self.calibration_coefficient,
        )
        solver.calculate_energy_from_storage_temp()

        logger.debug(solver)
        return solver.energy_kWh

    def _max_storage_temp_to_energy(self, time_slot: DateTime) -> float:
        """
        Return the energy needed to be consumed by the heatpump in order to generate enough heat
        to warm the water tank to its maximum temperature.
        """

        tank_parameters = [
            TankSolverParameters(
                tank_volume_L=tank.tank_volume_L,
                current_storage_temp_C=self._tanks_state[tank_index].get_storage_temp_C(time_slot),
                target_storage_temp_C=tank.max_temp_C,
                temp_differential_per_sec=None,
            )
            for tank_index, tank in enumerate(self._tank_parameters)
        ]

        solver = HeatpumpStorageEnergySolver(
            tank_parameters=tank_parameters,
            dh_supply_temp_C=self._water_supply_temp_C.get_value(time_slot),
            dh_return_temp_C=self._water_return_temp_C.get_value(time_slot),
            dh_flow_m3_per_hour=self._dh_water_flow_m3.get_value(time_slot),
            calibration_coefficient=self.calibration_coefficient,
        )
        solver.calculate_energy_from_storage_temp()

        logger.debug(solver)
        return solver.energy_kWh

    def _energy_to_target_storage_temp(self, energy_kWh: float, time_slot: DateTime) -> float:
        """
        Return the water storage temperature after the heatpump has consumed energy_kWh energy and
        produced heat with it.
        """
        # pylint: disable=too-many-locals
        solver = HeatpumpStorageEnergySolver(
            tank_volume_l=self._tank_volume_l,
            current_storage_temp_C=self.state.get_storage_temp_C(time_slot),
            dh_supply_temp_C=self._water_supply_temp_C.get_value(time_slot),
            dh_return_temp_C=self._water_return_temp_C.get_value(time_slot),
            dh_flow_m3_per_hour=self._dh_water_flow_m3.get_value(time_slot),
            energy_kWh=energy_kWh,
            calibration_coefficient=self.calibration_coefficient,
        )
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
                    last_time_slot, self._calc_temp_increase_K(last_time_slot, energy_kWh)
                )

            # Update last slot statistics (COP, heat demand, condenser temp)
            target_storage_temp_C = self.state.get_storage_temp_C(time_slot)
            solver = HeatpumpStorageEnergySolver(
                tank_parameters=TankSolverParameters(),
                tank_volume_l=self._tank_volume_l,
                current_storage_temp_C=self.state.get_storage_temp_C(last_time_slot),
                dh_supply_temp_C=self._water_supply_temp_C.get_value(last_time_slot),
                dh_return_temp_C=self._water_return_temp_C.get_value(last_time_slot),
                dh_flow_m3_per_hour=self._dh_water_flow_m3.get_value(last_time_slot),
                target_storage_temp_C=target_storage_temp_C,
                calibration_coefficient=self.calibration_coefficient,
            )
            solver.calculate_energy_from_storage_temp()
            self.state.set_cop(last_time_slot, solver.cop)
            self.state.set_condenser_temp(last_time_slot, solver.condenser_temp_C)
            self.state.set_heat_demand(last_time_slot, solver.q_out_J)

        self.state.update_storage_temp(time_slot)

        self._set_temp_decrease_for_all_tanks(time_slot)

        # self.state.set_temp_decrease_K(
        #     time_slot, self._calc_temp_decrease_K(time_slot))

        self._calc_energy_demand(time_slot)

    def event_market_cycle(self, current_time_slot):
        """To be called at the start of the market slot."""
        self._rotate_profiles(current_time_slot)
        self._populate_state(current_time_slot)
        supply_temp = self._water_supply_temp_C.get_value(current_time_slot)
        return_temp = self._water_return_temp_C.get_value(current_time_slot)
        assert supply_temp >= return_temp, (
            f"Supply temperature {supply_temp} has to be greater "
            f"than {return_temp}, timeslot {current_time_slot}"
        )
