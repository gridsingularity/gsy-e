from dataclasses import dataclass
import logging
from statistics import mean
from typing import Dict, Union, List

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from pendulum import DateTime

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.state import HeatPumpTankState
from gsy_e.models.strategy.energy_parameters.virtual_heatpump_solver import (
    TankSolverParameters,
    VirtualHeatpumpSolverParameters,
    HeatpumpStorageEnergySolver,
)

logger = logging.getLogger(__name__)


WATER_SPECIFIC_HEAT_CAPACITY = 4182  # [J/kg°C]
SPECIFIC_HEAT_CONST_WATER = 0.00116  # [kWh / (K * kg)]
WATER_DENSITY = 1  # [kg / l]


@dataclass
class TankParameters:
    min_temp_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C
    max_temp_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C
    initial_temp_C: float = ConstSettings.HeatPumpSettings.INIT_TEMP_C
    tank_volume_L: float = ConstSettings.HeatPumpSettings.TANK_VOL_L


class TankEnergyParameters:
    def __init__(self, tank_parameters: TankParameters, slot_length):
        self._parameters = tank_parameters
        self._state = HeatPumpTankState(
            initial_temp_C=tank_parameters.initial_temp_C,
            slot_length=slot_length,
            min_storage_temp_C=tank_parameters.min_temp_C,
            max_storage_temp_C=tank_parameters.max_temp_C,
        )

    def max_desired_temp_diff(self, time_slot):
        return (
            self._parameters.max_temp_C
            - self._state.get_storage_temp_C(time_slot)
            + self._state.get_temp_decrease_K(time_slot)
        )

    @property
    def _Q_specific(self):
        return SPECIFIC_HEAT_CONST_WATER * self._parameters.tank_volume_L * WATER_DENSITY

    def serialize(self):
        return {
            "max_temp_C": self._parameters.max_temp_C,
            "min_temp_C": self._parameters.min_temp_C,
            "tank_volume_l": self._parameters.tank_volume_L,
        }

    def increase_tank_temp(self, heat_energy: float, time_slot: DateTime):
        temp_increase_K = self._Q_kWh_to_temp_diff(heat_energy)
        self._state.update_temp_increase_K(time_slot, temp_increase_K)

    def decrease_tank_temp(self, heat_energy: float, time_slot: DateTime):
        temp_decrease_K = self._Q_kWh_to_temp_diff(heat_energy)
        self._state.set_temp_decrease_K(time_slot, temp_decrease_K)

    def update_tank_temp_vhp(self, temp_diff: float, time_slot: DateTime):
        return temp_diff + self._state.get_temp_decrease_K(time_slot)

    def decrease_tank_temp_vhp(self, heat_energy: float, time_slot: DateTime):
        """
        Decrease the tank temperature. Return True if the operation incurs in unmatched demand.
        """
        temp_differential_per_sec = -heat_energy / (
            WATER_DENSITY * WATER_SPECIFIC_HEAT_CAPACITY * self._parameters.tank_volume_L
        )
        temp_decrease_C = temp_differential_per_sec * GlobalConfig.slot_length.total_seconds()
        # Temp decrease is a negative value, therefore we need to add it to the current temp.
        new_temperature_without_operation_C = (
            self._state.get_storage_temp_C(time_slot) + temp_decrease_C
        )
        if new_temperature_without_operation_C < self._parameters.min_temp_C:
            # Tank temp drops below minimum. Setting zero to tank temperature and reporting the
            # unmatched heat demand event in order to be calculated and tracked.
            self._state.set_temp_decrease_K(time_slot, 0.0)
            return True
        assert temp_decrease_C <= 0.0
        self._state.set_temp_decrease_K(time_slot, abs(temp_decrease_C))
        return False

    def get_max_energy_consumption(self, cop: float, time_slot: DateTime):
        max_desired_temp_diff = (
            self._parameters.max_temp_C
            - self._state.get_storage_temp_C(time_slot)
            + self._state.get_temp_decrease_K(time_slot)
        )
        return max_desired_temp_diff * self._Q_specific / cop

    def get_min_energy_consumption(self, cop: float, time_slot: DateTime):
        return self._state.get_temp_decrease_K(time_slot) * self._Q_specific / cop

    def current_tank_temperature(self, time_slot: DateTime) -> float:
        return self._state.get_storage_temp_C(time_slot)

    def get_unmatched_demand_kWh(self, time_slot: DateTime) -> float:
        temp_balance = self._state.get_temp_increase_K(
            time_slot
        ) - self._state.get_temp_decrease_K(time_slot)
        if temp_balance < FLOATING_POINT_TOLERANCE:
            return self._temp_diff_to_Q_kWh(abs(temp_balance))
        else:
            return 0.0

    def create_tank_parameters_for_maintaining_tank_temp(
        self, time_slot: DateTime
    ) -> TankSolverParameters:
        current_storage_temp_C = self._state.get_storage_temp_C(time_slot)
        target_storage_temp_C = current_storage_temp_C
        if not self._parameters.min_temp_C < target_storage_temp_C < self._parameters.max_temp_C:
            logger.info(
                "Storage temp %s cannot exceed min (%s) / max (%s) tank temperatures.",
                target_storage_temp_C,
                self._parameters.min_temp_C,
                self._parameters.max_temp_C,
            )
            target_storage_temp_C = max(
                min(target_storage_temp_C, self._parameters.max_temp_C),
                self._parameters.min_temp_C,
            )
        return TankSolverParameters(
            tank_volume_L=self._parameters.tank_volume_L,
            current_storage_temp_C=current_storage_temp_C,
            target_storage_temp_C=target_storage_temp_C,
        )

    def create_tank_parameters_for_maxing_tank_temp(
        self, time_slot: DateTime
    ) -> TankSolverParameters:
        current_storage_temp_C = self._state.get_storage_temp_C(time_slot)
        target_storage_temp_C = self._parameters.max_temp_C
        return TankSolverParameters(
            tank_volume_L=self._parameters.tank_volume_L,
            current_storage_temp_C=current_storage_temp_C,
            target_storage_temp_C=target_storage_temp_C,
        )

    def create_tank_parameters_without_target_tank_temp(self, time_slot: DateTime):
        current_storage_temp_C = self._state.get_storage_temp_C(time_slot)
        return TankSolverParameters(
            tank_volume_L=self._parameters.tank_volume_L,
            current_storage_temp_C=current_storage_temp_C,
        )

    def _temp_diff_to_Q_kWh(self, diff_temp_K: float) -> float:
        return diff_temp_K * self._Q_specific

    def _Q_kWh_to_temp_diff(self, energy_kWh: float) -> float:
        return energy_kWh / self._Q_specific


class AllTanksEnergyParameters:
    def __init__(self, tank_parameters: List[TankParameters]):
        self._tanks_energy_parameters = [
            TankEnergyParameters(tank, GlobalConfig.slot_length) for tank in tank_parameters
        ]

    def increase_tanks_temp(self, heat_energy: float, time_slot: DateTime):
        # Split heat energy equally across tanks
        heat_energy_per_tank = heat_energy / len(self._tanks_energy_parameters)
        for tank in self._tanks_energy_parameters:
            tank.increase_tank_temp(heat_energy_per_tank, time_slot)

    def set_temp_decrease(self, heat_energy: float, time_slot: DateTime):
        heat_energy_per_tank = heat_energy / len(self._tanks_energy_parameters)
        for tank in self._tanks_energy_parameters:
            tank.decrease_tank_temp(heat_energy_per_tank, time_slot)

    def set_temp_decrease_vhp(
        self, heat_energy: float, time_slot: DateTime
    ) -> List[TankSolverParameters]:
        """
        Decrease the temperature of all tanks according to the heat energy produced.
        Returns true if there is unmatched heat demand in any of the tanks.
        """
        heat_energy_per_tank = heat_energy / len(self._tanks_energy_parameters)
        unmatched_heat_demand = [
            tank.decrease_tank_temp_vhp(heat_energy_per_tank, time_slot)
            for tank in self._tanks_energy_parameters
        ]
        # TODO: Implemented the current behavior, which is wrong because setting the current tank
        # temp to target tank temp ignores the energy that is already consumed from the heatpump
        # and the corresponding temp increase.
        if any(unmatched_heat_demand):
            return self.create_tank_parameters_for_maintaining_tank_temperature(time_slot)
        return []

    def update_tanks_temperature(self, time_slot: DateTime):
        for tank in self._tanks_energy_parameters:
            tank._state.update_storage_temp(time_slot)

    def get_max_energy_consumption(self, cop: float, time_slot: DateTime):
        max_energy_consumption_kWh = sum(
            tank.get_max_energy_consumption(cop, time_slot)
            for tank in self._tanks_energy_parameters
        )
        assert max_energy_consumption_kWh > -FLOATING_POINT_TOLERANCE
        return max_energy_consumption_kWh

    def get_min_energy_consumption(self, cop: float, time_slot: DateTime):
        min_energy_consumption_kWh = sum(
            tank.get_min_energy_consumption(cop, time_slot)
            for tank in self._tanks_energy_parameters
        )
        assert min_energy_consumption_kWh > -FLOATING_POINT_TOLERANCE
        return min_energy_consumption_kWh

    def get_average_tank_temperature(self, time_slot: DateTime):
        return mean(
            tank.current_tank_temperature(time_slot) for tank in self._tanks_energy_parameters
        )

    def get_unmatched_demand_kWh(self, time_slot: DateTime):
        return sum(
            tank.get_unmatched_demand_kWh(time_slot) for tank in self._tanks_energy_parameters
        )

    def serialize(self) -> Union[Dict, List]:
        if len(self._tanks_energy_parameters) == 1:
            # Return a dict for the case of one tank, in order to not break other services that
            # support one single tank.
            return self._tanks_energy_parameters[0].serialize()
        return [tank.serialize() for tank in self._tanks_energy_parameters]

    def create_tank_parameters_for_maintaining_tank_temperature(
        self, time_slot: DateTime
    ) -> List[TankSolverParameters]:
        return [
            tank.create_tank_parameters_for_maintaining_tank_temp(time_slot)
            for tank in self._tanks_energy_parameters
        ]

    def create_tank_parameters_for_maxing_tank_temperature(
        self, time_slot: DateTime
    ) -> List[TankSolverParameters]:
        return [
            tank.create_tank_parameters_for_maxing_tank_temp(time_slot)
            for tank in self._tanks_energy_parameters
        ]

    def update_tanks_temperature_with_energy(
        self, heatpump_parameters: VirtualHeatpumpSolverParameters, time_slot: DateTime
    ) -> HeatpumpStorageEnergySolver:
        tank_parameters = [
            tank.create_tank_parameters_without_target_tank_temp(time_slot)
            for tank in self._tanks_energy_parameters
        ]
        solver = HeatpumpStorageEnergySolver(
            heatpump_parameters=heatpump_parameters, tank_parameters=tank_parameters
        )
        solver.calculate_storage_temp_from_energy()
        logger.debug(solver)

        for tank_index, tank_output in enumerate(solver.tank_parameters):
            self._tanks_energy_parameters[tank_index].update_tank_temp_vhp(
                tank_output.target_storage_temp_C - tank_output.current_storage_temp_C, time_slot
            )

        return solver
