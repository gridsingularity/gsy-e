import logging
from dataclasses import dataclass
from typing import Optional, List

import sympy as sp
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.utils import convert_W_to_kWh, convert_kWh_to_W

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.energy_parameters.heatpump_constants import (
    WATER_SPECIFIC_HEAT_CAPACITY,
    WATER_DENSITY,
)

logger = logging.getLogger(__name__)


@dataclass
class VirtualHeatpumpSolverParameters:
    """Sympy solver parameters for the Heatpump."""

    dh_supply_temp_C: float
    dh_return_temp_C: float
    dh_flow_m3_per_hour: float
    source_temp_C: float
    calibration_coefficient: float = ConstSettings.HeatPumpSettings.CALIBRATION_COEFFICIENT
    energy_kWh: Optional[float] = None

    def __str__(self):
        return (
            f"Supply temp: {self.dh_supply_temp_C} "
            f"Return temp: {self.dh_return_temp_C} "
            f"Water Flow: {self.dh_flow_m3_per_hour} "
            f"Calibration Coefficient: {self.calibration_coefficient} "
            f"Energy: {self.energy_kWh}"
            f"Source temp: {self.source_temp_C}"
        )


@dataclass
class TankSolverParameters:
    """Sympy solver parameters for the water tank."""

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


class VirtualHeatpumpStorageEnergySolver:
    # pylint: disable=too-many-instance-attributes,too-many-arguments
    """Solver that calculates heatpump storage temperature and energy."""

    def __init__(
        self,
        tank_parameters: List[TankSolverParameters],
        heatpump_parameters: VirtualHeatpumpSolverParameters,
    ):
        # Optional inputs
        self.energy_kWh = heatpump_parameters.energy_kWh
        # Inputs
        self.tank_parameters = tank_parameters
        self.heatpump_parameters = heatpump_parameters
        self.dh_supply_temp_C = heatpump_parameters.dh_supply_temp_C
        self.dh_return_temp_C = heatpump_parameters.dh_return_temp_C
        self.dh_flow_kg_per_sec = heatpump_parameters.dh_flow_m3_per_hour * 1000 / 3600
        self.source_temp_C = heatpump_parameters.source_temp_C
        if self.dh_flow_kg_per_sec < FLOATING_POINT_TOLERANCE:
            self.dh_flow_kg_per_sec = 0
        # Outputs
        self.q_out_J = None
        self.q_in_J = None
        self.condenser_temp_C = None
        self.cop = None
        self.p_el_W = None
        self.calibration_coefficient = heatpump_parameters.calibration_coefficient

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
            ) + (
                sum(tank.target_storage_temp_C for tank in self.tank_parameters)
                / len(self.tank_parameters)
            )
            print("self.source_temp_C", self.source_temp_C)
            self.cop = self.calibration_coefficient * (
                self.condenser_temp_C
                / (self.condenser_temp_C - self.heatpump_parameters.source_temp_C)
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
                    * tank_symbols[(2 * tank_index) + 1]
                )
                for tank_index, tank in enumerate(self.tank_parameters)
            ]
        )
        print("ff", self.heatpump_parameters.source_temp_C)
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
                    * (
                        condenser_temp_sym
                        / (condenser_temp_sym - self.heatpump_parameters.source_temp_C)
                    ),
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
            tank.temp_differential_per_sec = float(solution.get(tank_symbols[2 * tank_index + 1]))
        self.condenser_temp_C = float(solution.get(condenser_temp_sym))
