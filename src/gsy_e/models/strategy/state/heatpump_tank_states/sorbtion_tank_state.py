import logging
from pendulum import DateTime, duration

from gsy_framework.constants_limits import GlobalConfig
from gsy_e.models.strategy.energy_parameters.heatpump.tank_parameters import TankParameters
from gsy_e.models.strategy.state.base_states import TankStateBase

log = logging.getLogger()

class SorptionTankState(TankStateBase):

    def __init__(
            self,
            tank_parameters: TankParameters,
    ):
        super().__init__(tank_parameters)
        self._currently_charging: bool = False
        self._time_since_start_cycle: duration = duration(minutes=0)


    def toggle_charging(self, charge=True):
        if self._is_charging_cycle_completed:
            self._currently_charging = charge
            self._time_since_start_cycle = duration(minutes=0)

    def set_time(self, time_slot: DateTime):
        super().set_time(time_slot)


    def no_charge(self, time_slot: DateTime):
        self._soc[time_slot] = self._soc[self._last_time_slot(time_slot)]

    def increase_tank_temp_from_heat_energy(self, heat_energy_kWh: float, time_slot: DateTime):
        if not self._currently_charging:
            log.error("should not charge")
        pass

    def decrease_tank_temp_from_heat_energy(self, heat_energy_kWh: float, time_slot: DateTime):
        if self._currently_charging:
            log.error("should not discharge")
        pass

    def get_min_heat_energy_consumption_kJ(self, time_slot: DateTime, heat_demand_kJ: float):
        if not self._currently_charging:
            return 0
        return heat_demand_kJ # todo

    def get_max_heat_energy_consumption_kJ(self, time_slot: DateTime, heat_demand_kJ: float):
        if not self._currently_charging:
            return 0
        return heat_demand_kJ # todo

    def get_dod_energy_kJ(self, time_slot: DateTime) -> float:
        if not self._currently_charging:
            return 0
        return super().get_dod_energy_kJ(time_slot)

    def get_available_energy_kJ(self, time_slot: DateTime) -> float:
        if self._currently_charging:
            return 0
        return super().get_available_energy_kJ(time_slot)

    def _is_charging_cycle_completed(self) -> bool:
        # 1. is soc at 100% (or configurable value)
        # is self._time_since_start_cycle > minimal_cycle_time
        return True

    def reset_time_since_start_cycle
