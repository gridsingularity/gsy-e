from collections import defaultdict
from logging import getLogger
from typing import Dict

from gsy_framework.utils import (
    convert_pendulum_to_str_in_dict,
    convert_str_to_pendulum_in_dict,
    convert_kWh_to_kJ,
    convert_kJ_to_kWh,
)
from gsy_framework.constants_limits import GlobalConfig
from pendulum import DateTime

from gsy_e import constants
from gsy_e.models.strategy.energy_parameters.heatpump.constants import (
    WATER_DENSITY,
    SPECIFIC_HEAT_CONST_WATER,
)
from gsy_e.models.strategy.energy_parameters.heatpump.tank_parameters import TankParameters
from gsy_e.models.strategy.state.base_states import TankStateBase
from gsy_e.models.strategy.state.heatpump_state import delete_time_slots_in_state

log = getLogger(__name__)


class WaterTankState(TankStateBase):
    """State for the heat pump tank."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, tank_parameters: TankParameters):
        super().__init__(tank_parameters)
        self._storage_temp_C: Dict[DateTime, float] = defaultdict(
            lambda: tank_parameters.initial_temp_C
        )
        self._max_capacity_kJ = convert_kWh_to_kJ(
            (self._params.max_temp_C - self._params.min_temp_C) * self._Q_specific
        )

    def get_storage_temp_C(self, time_slot: DateTime) -> float:
        """Return temperature of storage for a time slot in degree Celsius."""
        return self._storage_temp_C[time_slot]

    def _update_soc(self, time_slot: DateTime):
        self._soc[time_slot] = (self._storage_temp_C[time_slot] - self._params.min_temp_C) / (
            self._params.max_temp_C - self._params.min_temp_C
        )

    def get_state(self) -> Dict:
        return {
            "storage_temp_C": convert_pendulum_to_str_in_dict(self._storage_temp_C),
            "soc": convert_pendulum_to_str_in_dict(self._soc),
        }

    def restore_state(self, state_dict: Dict):
        self._storage_temp_C = convert_str_to_pendulum_in_dict(state_dict["storage_temp_C"])
        self._soc = convert_str_to_pendulum_in_dict(state_dict["soc"])

    def delete_past_state_values(self, current_time_slot: DateTime):
        if not current_time_slot or constants.RETAIN_PAST_MARKET_STRATEGIES_STATE:
            return
        last_time_slot = self._last_time_slot(current_time_slot)
        self._delete_time_slots(self._storage_temp_C, last_time_slot)
        self._delete_time_slots(self._soc, last_time_slot)

    def get_results_dict(self, current_time_slot: DateTime) -> Dict:
        return {
            "storage_temp_C": self.get_storage_temp_C(current_time_slot),
            "soc": self.get_soc(current_time_slot),
            "type": "WATER",
        }

    def __str__(self):
        return self.__class__.__name__

    def serialize(self):
        """Serializable dict with the parameters of the water tank."""
        return {
            "max_temp_C": self._params.max_temp_C,
            "min_temp_C": self._params.min_temp_C,
            "tank_volume_l": self._params.tank_volume_L,
        }

    def increase_tank_temp_from_heat_energy(self, heat_energy_kWh: float, time_slot: DateTime):
        """Increase the temperature of the water tank with the provided heat energy."""
        temp_increase_K = self._Q_kWh_to_temp_diff(heat_energy_kWh)
        new_temp = self.get_storage_temp_C(self._last_time_slot(time_slot)) + temp_increase_K
        if new_temp > self._params.max_temp_C:
            new_temp = self._params.max_temp_C
            log.warning("Storage tank temperature exceeded maximum, setting to maximum.")
        self._storage_temp_C[time_slot] = new_temp
        self._update_soc(time_slot)

    def decrease_tank_temp_from_heat_energy(self, heat_energy_kWh: float, time_slot: DateTime):
        """Decrease the temperature of the water tank with the provided heat energy."""
        temp_decrease_K = self._Q_kWh_to_temp_diff(heat_energy_kWh)
        new_temp = self.get_storage_temp_C(self._last_time_slot(time_slot)) - temp_decrease_K
        if new_temp < self._params.min_temp_C:
            new_temp = self._params.min_temp_C
            log.warning("Storage tank temperature dropped below minimum, setting to minimum.")
        self._storage_temp_C[time_slot] = new_temp
        self._update_soc(time_slot)

    def no_charge(self, time_slot: DateTime):
        self._storage_temp_C[time_slot] = self.get_storage_temp_C(self._last_time_slot(time_slot))
        self._update_soc(time_slot)

    def get_max_heat_energy_consumption_kJ(self, time_slot: DateTime, heat_demand_kJ: float):
        """Calculate max heat energy consumption that the tank can accomodate."""
        temp_diff_due_to_consumption = self._Q_kWh_to_temp_diff(convert_kJ_to_kWh(heat_demand_kJ))
        max_temp_diff = (
            self._params.max_temp_C
            - self.get_storage_temp_C(time_slot)
            + temp_diff_due_to_consumption
        )
        if max_temp_diff < 0:
            assert False
        return convert_kWh_to_kJ(max_temp_diff * self._Q_specific)

    def get_min_heat_energy_consumption_kJ(self, time_slot: DateTime, heat_demand_kJ: float):
        """
        Calculate min heat energy consumption that a heatpump has to consume in
        order to only let the storage drop its temperature to the minimum storage temperature.
        - if current_temp < min_storage_temp: charge till min_storage_temp is reached
        - if current_temp = min_storage_temp: only for the demanded energy
        - if current_temp > min_storage: only trade for the demand minus the heat
                                         that can be extracted from the storage
        """
        diff_to_min_temp_C = self.get_storage_temp_C(time_slot) - self._params.min_temp_C
        temp_diff_due_to_consumption = self._Q_kWh_to_temp_diff(convert_kJ_to_kWh(heat_demand_kJ))
        min_temp_diff = (
            temp_diff_due_to_consumption - diff_to_min_temp_C
            if diff_to_min_temp_C <= temp_diff_due_to_consumption
            else 0
        )
        return convert_kWh_to_kJ(min_temp_diff * self._Q_specific)

    def current_tank_temperature(self, time_slot: DateTime) -> float:
        """Get current tank temperature for timeslot."""
        return self.get_storage_temp_C(time_slot)

    def _Q_kWh_to_temp_diff(self, energy_kWh: float) -> float:
        return energy_kWh / self._Q_specific

    @property
    def _Q_specific(self):
        return SPECIFIC_HEAT_CONST_WATER * self._params.tank_volume_L * WATER_DENSITY

    @staticmethod
    def _delete_time_slots(profile: Dict, current_time_stamp: DateTime):
        delete_time_slots_in_state(profile, current_time_stamp)

    def init(self):
        self._update_soc(GlobalConfig.start_date)
