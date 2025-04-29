import logging
from typing import List

from gsy_framework.constants_limits import GlobalConfig
from pendulum import DateTime

from gsy_e.models.strategy.energy_parameters.heatpump.constants import (
    WATER_SPECIFIC_HEAT_CAPACITY,
    WATER_DENSITY,
)
from gsy_e.models.strategy.state.heatpump_all_tanks_state import AllTanksState
from gsy_e.models.strategy.energy_parameters.heatpump.tank_parameters import TankParameters
from gsy_e.models.strategy.state.heatpump_water_tank_state import WaterTankState
from gsy_e.models.strategy.energy_parameters.heatpump.virtual_heatpump_solver import (
    TankSolverParameters,
    VirtualHeatpumpSolverParameters,
    VirtualHeatpumpStorageEnergySolver,
)

logger = logging.getLogger(__name__)


class VirtualHeatpumpTankState(WaterTankState):
    """
    Individual tank energy parameters, for operation with the virtual heatpump.
    Uses the sympy solver in order to model the water tank.
    """

    def decrease_tank_temp_vhp(self, heat_energy: float, time_slot: DateTime):
        """
        Decrease the tank temperature. Return True if the operation incurs in unmatched demand.
        """
        temp_differential_per_sec = -heat_energy / (
            WATER_DENSITY * WATER_SPECIFIC_HEAT_CAPACITY * self._params.tank_volume_L
        )
        temp_decrease_C = temp_differential_per_sec * GlobalConfig.slot_length.total_seconds()
        # Temp decrease is a negative value, therefore we need to add it to the current temp.
        new_temperature_without_operation_C = self.get_storage_temp_C(time_slot) + temp_decrease_C
        if new_temperature_without_operation_C < self._params.min_temp_C:
            # Tank temp drops below minimum. Setting zero to tank temperature and reporting the
            # unmatched heat demand event in order to be calculated and tracked.
            self.set_temp_decrease_K(time_slot, 0.0)
            return True
        assert temp_decrease_C <= 0.0
        self.set_temp_decrease_K(time_slot, abs(temp_decrease_C))
        return False

    def create_tank_parameters_for_maintaining_tank_temp(
        self, time_slot: DateTime
    ) -> TankSolverParameters:
        """
        Return tank solver parameters, that can be used by the solver to maintain the current tank
        temp.
        """
        current_storage_temp_C = self.get_storage_temp_C(time_slot)
        target_storage_temp_C = current_storage_temp_C
        if not self._params.min_temp_C < target_storage_temp_C < self._params.max_temp_C:
            logger.info(
                "Storage temp %s cannot exceed min (%s) / max (%s) tank temperatures.",
                target_storage_temp_C,
                self._params.min_temp_C,
                self._params.max_temp_C,
            )
            target_storage_temp_C = max(
                min(target_storage_temp_C, self._params.max_temp_C),
                self._params.min_temp_C,
            )
        return TankSolverParameters(
            tank_volume_L=self._params.tank_volume_L,
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
        current_storage_temp_C = self.get_storage_temp_C(time_slot)
        target_storage_temp_C = self._params.max_temp_C
        return TankSolverParameters(
            tank_volume_L=self._params.tank_volume_L,
            current_storage_temp_C=current_storage_temp_C,
            target_storage_temp_C=target_storage_temp_C,
        )

    def create_tank_parameters_without_target_tank_temp(self, time_slot: DateTime):
        """
        Create tank parameters without specifying tank temp, in order to be used as an output of
        the solver.
        """
        current_storage_temp_C = self.get_storage_temp_C(time_slot)
        return TankSolverParameters(
            tank_volume_L=self._params.tank_volume_L,
            current_storage_temp_C=current_storage_temp_C,
        )


class VirtualHeatpumpAllTanksState(AllTanksState):
    """Manage the operation of all tanks for the virtual heatpump. Uses sympy solver."""

    # pylint: disable=super-init-not-called
    def __init__(self, tank_parameters: List[TankParameters]):
        self.tanks_states = [VirtualHeatpumpTankState(tank) for tank in tank_parameters]

    def set_temp_decrease_vhp(
        self, heat_energy: float, time_slot: DateTime
    ) -> List[TankSolverParameters]:
        """
        Decrease the temperature of all tanks according to the heat energy produced.
        Returns true if there is unmatched heat demand in any of the tanks.
        """
        heat_energy_per_tank = heat_energy / len(self.tanks_states)
        unmatched_heat_demand = [
            tank.decrease_tank_temp_vhp(heat_energy_per_tank, time_slot)
            for tank in self.tanks_states
        ]
        if any(unmatched_heat_demand):
            return self.create_tank_solver_for_maintaining_tank_temperature(time_slot)
        return []

    def create_tank_solver_for_maintaining_tank_temperature(
        self, time_slot: DateTime
    ) -> List[TankSolverParameters]:
        """
        Return tank solver parameters for all water tanks, that can be used by the solver to
        maintain all current tanks' temp.
        """
        return [
            tank.create_tank_parameters_for_maintaining_tank_temp(time_slot)
            for tank in self.tanks_states
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
            for tank in self.tanks_states
        ]

    def increase_tanks_temperature_with_energy_vhp(
        self, heatpump_parameters: VirtualHeatpumpSolverParameters, time_slot: DateTime
    ) -> VirtualHeatpumpStorageEnergySolver:
        """
        Increase tank temperature from energy, provided as part of the heatpump parameters.
        """
        tank_parameters = [
            tank.create_tank_parameters_without_target_tank_temp(time_slot)
            for tank in self.tanks_states
        ]
        solver = VirtualHeatpumpStorageEnergySolver(
            heatpump_parameters=heatpump_parameters, tank_parameters=tank_parameters
        )
        solver.calculate_storage_temp_from_energy()
        logger.debug(solver)

        for tank_index, tank_output in enumerate(solver.tank_parameters):
            self.tanks_states[tank_index].increase_tank_temp_from_temp_delta(
                tank_output.target_storage_temp_C - tank_output.current_storage_temp_C, time_slot
            )

        return solver
