from dataclasses import dataclass
import logging
from statistics import mean
from typing import Dict, Union, List

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from pendulum import DateTime

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.state import HeatPumpTankState
from gsy_e.models.strategy.energy_parameters.heatpump_constants import (
    WATER_SPECIFIC_HEAT_CAPACITY,
    WATER_DENSITY,
    SPECIFIC_HEAT_CONST_WATER,
)
from gsy_e.models.strategy.energy_parameters.virtual_heatpump_solver import (
    TankSolverParameters,
    VirtualHeatpumpSolverParameters,
    VirtualHeatpumpStorageEnergySolver,
)

logger = logging.getLogger(__name__)


@dataclass
class TankParameters:
    """Nameplate parameters of a water tank."""

    min_temp_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C
    max_temp_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C
    initial_temp_C: float = ConstSettings.HeatPumpSettings.INIT_TEMP_C
    tank_volume_L: float = ConstSettings.HeatPumpSettings.TANK_VOL_L


class TankEnergyParameters:
    """Manage the operation of heating and extracting temperature from a single tank."""

    def __init__(self, tank_parameters: TankParameters, slot_length):
        self._parameters = tank_parameters
        self._state = HeatPumpTankState(
            initial_temp_C=tank_parameters.initial_temp_C,
            slot_length=slot_length,
            min_storage_temp_C=tank_parameters.min_temp_C,
            max_storage_temp_C=tank_parameters.max_temp_C,
        )

    @property
    def _Q_specific(self):
        return SPECIFIC_HEAT_CONST_WATER * self._parameters.tank_volume_L * WATER_DENSITY

    def serialize(self):
        """Serializable dict with the parameters of the water tank."""
        return {
            "max_temp_C": self._parameters.max_temp_C,
            "min_temp_C": self._parameters.min_temp_C,
            "tank_volume_l": self._parameters.tank_volume_L,
        }

    def get_results_dict(self, current_time_slot: DateTime):
        """Results dict with the results from the tank."""
        return self._state.get_results_dict(current_time_slot)

    def increase_tank_temp_from_heat_energy(self, heat_energy: float, time_slot: DateTime):
        """Increase the temperature of the water tank with the provided heat energy."""
        temp_increase_K = self._Q_kWh_to_temp_diff(heat_energy)
        self._state.update_temp_increase_K(time_slot, temp_increase_K)

    def decrease_tank_temp_from_heat_energy(self, heat_energy: float, time_slot: DateTime):
        """Decrease the temperature of the water tank with the provided heat energy."""
        temp_decrease_K = self._Q_kWh_to_temp_diff(heat_energy)
        self._state.set_temp_decrease_K(time_slot, temp_decrease_K)

    def increase_tank_temp_from_temp_delta(self, temp_diff: float, time_slot: DateTime):
        """Increase the tank temperature from temperature delta."""
        self._state.update_temp_increase_K(time_slot, temp_diff)

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
        """Calculate max energy consumption that a heatpump with provided COP can consume."""
        max_temp_diff = (
            self._parameters.max_temp_C
            - self._state.get_storage_temp_C(time_slot)
            + self._state.get_temp_decrease_K(time_slot)
        )
        return max_temp_diff * self._Q_specific / cop

    def get_min_energy_consumption(self, cop: float, time_slot: DateTime):
        """Calculate min energy consumption that a heatpump with provided COP can consume."""
        return self._state.get_temp_decrease_K(time_slot) * self._Q_specific / cop

    def current_tank_temperature(self, time_slot: DateTime) -> float:
        """Get current tank temperature for timeslot."""
        return self._state.get_storage_temp_C(time_slot)

    def get_unmatched_demand_kWh(self, time_slot: DateTime) -> float:
        """Get unmatched demand for timeslot."""
        temp_balance = self._state.get_temp_increase_K(
            time_slot
        ) - self._state.get_temp_decrease_K(time_slot)
        if temp_balance < FLOATING_POINT_TOLERANCE:
            return self._temp_diff_to_Q_kWh(abs(temp_balance))
        return 0.0

    def create_tank_parameters_for_maintaining_tank_temp(
        self, time_slot: DateTime
    ) -> TankSolverParameters:
        """
        Return tank solver parameters, that can be used by the solver to maintain the current tank
        temp.
        """
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
        """
        Return tank solver parameters, that can be used by the solver to increase the current tank
        temp to its maximum.
        """
        current_storage_temp_C = self._state.get_storage_temp_C(time_slot)
        target_storage_temp_C = self._parameters.max_temp_C
        return TankSolverParameters(
            tank_volume_L=self._parameters.tank_volume_L,
            current_storage_temp_C=current_storage_temp_C,
            target_storage_temp_C=target_storage_temp_C,
        )

    def create_tank_parameters_without_target_tank_temp(self, time_slot: DateTime):
        """
        Create tank parameters without specifying tank temp, in order to be used as an output of
        the solver.
        """
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
    """Manage the operation of heating and extracting temperature from multiple tanks."""

    def __init__(self, tank_parameters: List[TankParameters]):
        self._tanks_energy_parameters = [
            TankEnergyParameters(tank, GlobalConfig.slot_length) for tank in tank_parameters
        ]

    def increase_tanks_temp_from_heat_energy(self, heat_energy: float, time_slot: DateTime):
        """Increase the temperature of the water tanks with the provided heat energy."""
        # Split heat energy equally across tanks
        heat_energy_per_tank = heat_energy / len(self._tanks_energy_parameters)
        for tank in self._tanks_energy_parameters:
            tank.increase_tank_temp_from_heat_energy(heat_energy_per_tank, time_slot)

    def decrease_tanks_temp_from_heat_energy(self, heat_energy: float, time_slot: DateTime):
        """Decrease the temperature of the water tanks with the provided heat energy."""
        heat_energy_per_tank = heat_energy / len(self._tanks_energy_parameters)
        for tank in self._tanks_energy_parameters:
            tank.decrease_tank_temp_from_heat_energy(heat_energy_per_tank, time_slot)

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
            return self.create_tank_solver_for_maintaining_tank_temperature(time_slot)
        return []

    def update_tanks_temperature(self, time_slot: DateTime):
        """
        Update the current temperature of all tanks, based on temp increase/decrease of the market
        slot.
        """
        for tank in self._tanks_energy_parameters:
            # pylint: disable=protected-access
            tank._state.update_storage_temp(time_slot)

    def get_max_energy_consumption(self, cop: float, time_slot: DateTime):
        """Get max energy consumption from all water tanks."""
        max_energy_consumption_kWh = sum(
            tank.get_max_energy_consumption(cop, time_slot)
            for tank in self._tanks_energy_parameters
        )
        assert max_energy_consumption_kWh > -FLOATING_POINT_TOLERANCE
        return max_energy_consumption_kWh

    def get_min_energy_consumption(self, cop: float, time_slot: DateTime):
        """Get min energy consumption from all water tanks."""
        min_energy_consumption_kWh = sum(
            tank.get_min_energy_consumption(cop, time_slot)
            for tank in self._tanks_energy_parameters
        )
        assert min_energy_consumption_kWh > -FLOATING_POINT_TOLERANCE
        return min_energy_consumption_kWh

    def get_average_tank_temperature(self, time_slot: DateTime):
        """Get average tank temperature of all water tanks."""
        return mean(
            tank.current_tank_temperature(time_slot) for tank in self._tanks_energy_parameters
        )

    def get_unmatched_demand_kWh(self, time_slot: DateTime):
        """Get unmatched demand of all water tanks."""
        return sum(
            tank.get_unmatched_demand_kWh(time_slot) for tank in self._tanks_energy_parameters
        )

    def create_tank_solver_for_maintaining_tank_temperature(
        self, time_slot: DateTime
    ) -> List[TankSolverParameters]:
        """
        Return tank solver parameters for all water tanks, that can be used by the solver to
        maintain all current tanks' temp.
        """
        return [
            tank.create_tank_parameters_for_maintaining_tank_temp(time_slot)
            for tank in self._tanks_energy_parameters
        ]

    def create_tank_parameters_for_maxing_tank_temperature(
        self, time_slot: DateTime
    ) -> List[TankSolverParameters]:
        """
        Return tank solver parameters for all water tanks, that can be used by the solver to
        increase all tanks' temp to its maximum.
        """
        return [
            tank.create_tank_parameters_for_maxing_tank_temp(time_slot)
            for tank in self._tanks_energy_parameters
        ]

    def increase_tanks_temperature_with_energy_vhp(
        self, heatpump_parameters: VirtualHeatpumpSolverParameters, time_slot: DateTime
    ) -> VirtualHeatpumpStorageEnergySolver:
        """
        Increase tank temperature from energy, provided as part of the heatpump parameters.
        """
        tank_parameters = [
            tank.create_tank_parameters_without_target_tank_temp(time_slot)
            for tank in self._tanks_energy_parameters
        ]
        solver = VirtualHeatpumpStorageEnergySolver(
            heatpump_parameters=heatpump_parameters, tank_parameters=tank_parameters
        )
        solver.calculate_storage_temp_from_energy()
        logger.debug(solver)

        for tank_index, tank_output in enumerate(solver.tank_parameters):
            self._tanks_energy_parameters[tank_index].increase_tank_temp_from_temp_delta(
                tank_output.target_storage_temp_C - tank_output.current_storage_temp_C, time_slot
            )

        return solver

    def serialize(self) -> Union[Dict, List]:
        """Serializable dict with the parameters of all water tanks."""
        if len(self._tanks_energy_parameters) == 1:
            # Return a dict for the case of one tank, in order to not break other services that
            # support one single tank.
            return self._tanks_energy_parameters[0].serialize()
        return [tank.serialize() for tank in self._tanks_energy_parameters]

    def get_results_dict(self, current_time_slot: DateTime):
        """Results dict with the results from all water tanks."""
        if len(self._tanks_energy_parameters) == 1:
            # Return a dict for the case of one tank, in order to not break other services that
            # support one single tank.
            return self._tanks_energy_parameters[0].get_results_dict(current_time_slot)
        return [tank.get_results_dict(current_time_slot) for tank in self._tanks_energy_parameters]

    def get_state(self) -> Union[List, Dict]:
        if len(self._tanks_energy_parameters) == 1:
            # Return a dict for the case of one tank, in order to not break other services that
            # support one single tank.
            return self._tanks_energy_parameters[0]._state.get_state()
        return [tank._state.get_state() for tank in self._tanks_energy_parameters]

    def restore_state(self, state_dict: dict):
        for tank in self._tanks_energy_parameters:
            tank._state.restore_state(state_dict)

    def delete_past_state_values(self, current_time_slot: DateTime):
        for tank in self._tanks_energy_parameters:
            tank._state.delete_past_state_values(current_time_slot)
