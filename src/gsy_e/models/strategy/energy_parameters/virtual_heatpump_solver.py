import logging
from typing import Optional

import sympy as sp
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.utils import convert_W_to_kWh, convert_kWh_to_W

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.energy_parameters.heat_pump_tank import WATER_DENSITY

logger = logging.getLogger(__name__)

WATER_SPECIFIC_HEAT_CAPACITY = 4182  # [J/kg°C]
GROUND_WATER_TEMPERATURE_C = 12


class HeatpumpStorageEnergySolver:
    # pylint: disable=too-many-instance-attributes,too-many-arguments
    """Solver that calculates heatpump storage temperature and energy."""

    def __init__(
        self,
        tank_volume_l: float,
        current_storage_temp_C: float,
        dh_supply_temp_C: float,
        dh_return_temp_C: float,
        dh_flow_m3_per_hour: float,
        target_storage_temp_C: Optional[float] = None,
        energy_kWh: Optional[float] = None,
        calibration_coefficient: float = ConstSettings.HeatPumpSettings.CALIBRATION_COEFFICIENT,
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
        assert self.target_storage_temp_C is not None
        self._calculate_q_out()

        self.temp_differential_per_sec = (
            self.target_storage_temp_C - self.current_storage_temp_C
        ) / GlobalConfig.slot_length.total_seconds()
        self.q_in_J = (
            WATER_DENSITY
            * WATER_SPECIFIC_HEAT_CAPACITY
            * self._tank_volume_l
            * self.temp_differential_per_sec
            + self.q_out_J
        )
        if self.dh_flow_kg_per_sec < FLOATING_POINT_TOLERANCE:
            self.condenser_temp_C = 0.0
            self.cop = 0.0
            self.p_el_W = 0.0
            self.energy_kWh = 0.0
        else:
            self.condenser_temp_C = (
                self.q_in_J / (self.dh_flow_kg_per_sec * WATER_SPECIFIC_HEAT_CAPACITY)
            ) + self.target_storage_temp_C
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

        (q_in_sym, cop_sym, storage_temp_sym, temp_differential_sym, condenser_temp_sym) = (
            sp.symbols("q_in, cop, storage_temp, temp_differential, condenser_temp")
        )

        ans = sp.solve(
            [
                sp.Eq(
                    (storage_temp_sym - self.current_storage_temp_C)
                    / GlobalConfig.slot_length.total_seconds(),
                    temp_differential_sym,
                ),
                sp.Eq(
                    WATER_DENSITY
                    * WATER_SPECIFIC_HEAT_CAPACITY
                    * self._tank_volume_l
                    * temp_differential_sym
                    + self.q_out_J,
                    q_in_sym,
                ),
                sp.Eq(
                    (q_in_sym / (self.dh_flow_kg_per_sec * WATER_SPECIFIC_HEAT_CAPACITY))
                    + storage_temp_sym,
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
        solution = max(ans, key=lambda result: result.get(temp_differential_sym))
        self.q_in_J = float(solution.get(q_in_sym))
        self.cop = float(solution.get(cop_sym))
        self.target_storage_temp_C = float(solution.get(storage_temp_sym))
        self.temp_differential_per_sec = float(solution.get(temp_differential_sym))
        self.condenser_temp_C = float(solution.get(condenser_temp_sym))
