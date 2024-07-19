from dataclasses import dataclass
from statistics import mean
from typing import Dict, Union, List

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.state import HeatPumpTankState
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from pendulum import DateTime


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

    def decrease_tank_temp_vhp(self, heat_energy: float, time_slot: DateTime):
        temp_differential_per_sec = -heat_energy / (
            WATER_DENSITY * WATER_SPECIFIC_HEAT_CAPACITY * self._parameters.tank_volume_L
        )
        temp_decrease_C = temp_differential_per_sec * GlobalConfig.slot_length.total_seconds()
        new_temperature_without_operation_C = (
            self._state.get_storage_temp_C(time_slot) - temp_decrease_C
        )
        if new_temperature_without_operation_C < self._parameters.min_temp_C:
            temp_decrease_C = 0.0
            self._calculate_and_set_unmatched_demand(time_slot)
        assert temp_decrease_C <= 0.0
        self._state.set_temp_decrease_K(time_slot, abs(temp_decrease_C))

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
