from typing import TYPE_CHECKING, Optional

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.enums import HeatPumpSourceType
from pendulum import DateTime

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.state import HeatPumpState
from gsy_e.models.strategy.profile import EnergyProfile

if TYPE_CHECKING:
    pass


SPECIFIC_HEAT_CONST_WATER = 0.000116  # [kWh K / kg]
WATER_DENSITY = 1  # [kg / l]


class HeatPumpEnergyParametersException(Exception):
    """Exception raised in the HeatPumpEnergyParameters"""


class HeatPumpEnergyParameters:
    """Energy Parameters for the heat pump."""
    # pylint: disable=too-many-instance-attributes, too-many-arguments
    def __init__(self,
                 maximum_power_rating_kW: float =
                 ConstSettings.HeatPumpSettings.MAX_POWER_RATING_KW,
                 min_temp_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C,
                 max_temp_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C,
                 initial_temp_C: float = ConstSettings.HeatPumpSettings.INIT_TEMP_C,
                 external_temp_C: Optional[float] = None,
                 external_temp_profile_uuid: Optional[str] = None,
                 tank_volume_l: float = ConstSettings.HeatPumpSettings.TANK_VOL_L,
                 consumption_kW: Optional[float] = None,
                 consumption_profile_uuid: Optional[str] = None,
                 source_type: int = ConstSettings.HeatPumpSettings.SOURCE_TYPE):

        self._min_temp_C = min_temp_C
        self._max_temp_C = max_temp_C
        self._source_type = source_type
        self._Q_specific = SPECIFIC_HEAT_CONST_WATER * tank_volume_l * WATER_DENSITY
        self._slot_length = GlobalConfig.slot_length
        self._max_energy_consumption = maximum_power_rating_kW * self._slot_length.total_hours()

        self.state = HeatPumpState(initial_temp_C)

        if not consumption_profile_uuid and not consumption_kW:
            consumption_kW = ConstSettings.HeatPumpSettings.CONSUMPTION_KW
        self._consumption_kW: [DateTime, float] = EnergyProfile(
            consumption_kW, consumption_profile_uuid)

        if not external_temp_profile_uuid and not external_temp_C:
            external_temp_C = ConstSettings.HeatPumpSettings.EXT_TEMP_C
        self._ext_temp_C: [DateTime, float] = EnergyProfile(
            external_temp_C, external_temp_profile_uuid)

    def serialize(self):
        """TODO"""
        return {
            "consumption_kW": self._consumption_kW.input_profile,
            "consumption_profile_uuid": self._consumption_kW.input_profile_uuid,
            "external_temp_C": self._ext_temp_C.input_profile,
            "external_temp_profile_uuid": self._ext_temp_C.input_profile_uuid
        }

    def event_activate(self):
        """Runs on activate event."""
        self._rotate_profiles()

    def event_market_cycle(self, current_time_slot):
        # if not current_time_slot:
        #     return
        self._rotate_profiles(current_time_slot)
        self._populate_state(current_time_slot)
        self.state.copy_to_next_slot(current_time_slot, self._slot_length)

    def event_traded_energy(self, time_slot: DateTime, energy_kWh: float):
        temp_diff = (self._calc_temp_increase(time_slot, energy_kWh) -
                     self.state.get_temp_decrease_K(time_slot))
        self.state.update_storage_temp(time_slot, temp_diff)

        self._decrement_posted_energy(time_slot, energy_kWh)

    def get_min_energy_demand_kWh(self, time_slot: DateTime) -> float:
        return self.state.get_min_energy_demand_kWh(time_slot)

    def get_max_energy_demand_kWh(self, time_slot: DateTime) -> float:
        return self.state.get_max_energy_demand_kWh(time_slot)

    def _rotate_profiles(self, current_time_slot: Optional[DateTime] = None):
        self._consumption_kW.read_or_rotate_profiles()
        self._ext_temp_C.read_or_rotate_profiles()

        self.state.delete_old_time_slots(current_time_slot)

    def _calc_energy_to_buy_greedy(self, time_slot: DateTime) -> float:
        max_energy_consumption = ((self._max_temp_C -
                                   self.state.get_storage_temp_C(time_slot) +
                                   self.state.get_temp_decrease_K(time_slot)) * self._Q_specific)
        return min(self._max_energy_consumption, max_energy_consumption)

    def _calc_energy_to_buy_minimum(self, time_slot: DateTime) -> float:
        max_temp_decrease_allowed = (
                self.state.get_storage_temp_C(time_slot) - self._min_temp_C)
        temp_diff = self.state.get_temp_decrease_K(time_slot) - max_temp_decrease_allowed
        min_energy_consumption = temp_diff * self._Q_specific
        return min(self._max_energy_consumption, min_energy_consumption)

    def _populate_state(self, time_slot: DateTime):
        # order matters here!
        self.state.update_temp_decrease_K(
            time_slot, self._calc_Q_consumption(
                time_slot, self._consumption_kW.profile[time_slot]) / self._Q_specific)
        self.state.set_min_energy_demand_kWh(
            time_slot, self._calc_energy_to_buy_minimum(time_slot))
        self.state.set_max_energy_demand_kWh(
            time_slot, self._calc_energy_to_buy_greedy(time_slot))

    def _calc_Q_consumption(self, time_slot: DateTime, consumption_kW: float) -> float:
        cop = self._calc_cop(self.state.get_storage_temp_C(time_slot),
                             self._ext_temp_C.profile[time_slot])
        return cop * consumption_kW

    def _calc_cop(self, temp_current: float, temp_ambient: float) -> float:
        delta_temp = temp_current - temp_ambient
        if self._source_type == HeatPumpSourceType.AIR.value:
            return 6.08 - 0.09 * delta_temp + 0.00005 * delta_temp**2
        elif self._source_type == HeatPumpSourceType.GROUND.value:
            return 10.29 - 0.21 * delta_temp + 0.0012 * delta_temp**2
        else:
            raise HeatPumpEnergyParametersException("HeatPumpSourceType not supported")

    def _calc_temp_increase(self, time_slot: DateTime, energy_kWh: float) -> float:
        return self._calc_Q_consumption(time_slot, energy_kWh) / self._Q_specific

    def _decrement_posted_energy(self, time_slot: DateTime, energy_kWh: float):
        updated_min_energy_demand_kWh = self.get_min_energy_demand_kWh(time_slot) - energy_kWh
        assert updated_min_energy_demand_kWh > -FLOATING_POINT_TOLERANCE
        updated_max_energy_demand_kWh = self.get_max_energy_demand_kWh(time_slot) - energy_kWh
        assert updated_max_energy_demand_kWh > -FLOATING_POINT_TOLERANCE

        self.state.set_min_energy_demand_kWh(time_slot, updated_min_energy_demand_kWh)
        self.state.set_max_energy_demand_kWh(time_slot, updated_max_energy_demand_kWh)
