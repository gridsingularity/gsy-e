from abc import ABC, abstractmethod
from typing import Optional, Dict, Union

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.enums import HeatPumpSourceType
from gsy_framework.read_user_profile import InputProfileTypes
from pendulum import DateTime

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.profile import EnergyProfile
from gsy_e.models.strategy.state import HeatPumpState

# pylint: disable=pointless-string-statement
"""
Description of physical units and parameters:
- K .. Kelvin:              Si unit, used for temperature differences
- C .. degrees celsius:     Used for temperatures
- Q .. heat/thermal energy: Energy that a body has or needs to have/get a certain temperature [kWh]
"""

SPECIFIC_HEAT_CONST_WATER = 0.00116  # [kWh / (K * kg)]
WATER_DENSITY = 1  # [kg / l]


class HeatPumpEnergyParametersException(Exception):
    """Exception raised in the HeatPumpEnergyParameters"""


class HeatPumpEnergyParametersBase(ABC):
    """
    Base class for common functionality across all heatpump strategies / models that include heat
    storage. Does not depend on a specific heatpump model, and cannot be instantiated on its own.
    """

    # pylint: disable=too-many-arguments, too-many-instance-attributes
    def __init__(
            self,
            maximum_power_rating_kW: float = ConstSettings.HeatPumpSettings.MAX_POWER_RATING_KW,
            min_temp_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C,
            max_temp_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C,
            initial_temp_C: float = ConstSettings.HeatPumpSettings.INIT_TEMP_C,
            tank_volume_l: float = ConstSettings.HeatPumpSettings.TANK_VOL_L):
        # As a precaution, clamp the initial temp value with the min and max allowed temp value
        initial_temp_C = min(max(min_temp_C, initial_temp_C), max_temp_C)
        self._min_temp_C = min_temp_C
        self._max_temp_C = max_temp_C
        self._tank_volume_l = tank_volume_l
        self._Q_specific = SPECIFIC_HEAT_CONST_WATER * tank_volume_l * WATER_DENSITY  # [kWh / K]
        self._slot_length = GlobalConfig.slot_length
        self._maximum_power_rating_kW = maximum_power_rating_kW
        self._max_energy_consumption_kWh = (
                maximum_power_rating_kW * self._slot_length.total_hours())
        self.state = HeatPumpState(initial_temp_C, self._slot_length)

    def event_activate(self):
        """Runs on activate event."""
        self._rotate_profiles()

    def event_market_cycle(self, current_time_slot):
        """To be called at the start of the market slot. """
        self._rotate_profiles(current_time_slot)
        self._populate_state(current_time_slot)

    def get_min_energy_demand_kWh(self, time_slot: DateTime) -> float:
        """Get energy that is needed to compensate for the heat los due to heating."""
        return self.state.get_min_energy_demand_kWh(time_slot)

    def get_max_energy_demand_kWh(self, time_slot: DateTime) -> float:
        """Get energy that is needed to heat up the storage to temp_max."""
        return self.state.get_max_energy_demand_kWh(time_slot)

    def serialize(self):
        """Return dict with the current energy parameter values."""
        return {
            "max_temp_C": self._max_temp_C,
            "min_temp_C": self._min_temp_C,
            "max_energy_consumption_kWh": self._max_energy_consumption_kWh,
            "maximum_power_rating_kW": self._maximum_power_rating_kW,
            "tank_volume_l": self._tank_volume_l
        }

    @abstractmethod
    def _rotate_profiles(self, current_time_slot: Optional[DateTime] = None):
        self.state.delete_past_state_values(current_time_slot)

    def _populate_state(self, time_slot: DateTime):
        self.state.update_storage_temp(time_slot)
        self.state.set_cop(time_slot, self._calc_cop(time_slot))

        self.state.set_temp_decrease_K(
            time_slot, self._calc_temp_decrease_K(time_slot))

        self._calc_energy_demand(time_slot)

    def _calc_cop(self, time_slot: DateTime) -> float:
        pass

    @abstractmethod
    def _calc_energy_to_buy_maximum(self, time_slot: DateTime) -> float:
        pass

    @abstractmethod
    def _calc_energy_to_buy_minimum(self, time_slot: DateTime) -> float:
        pass

    @abstractmethod
    def _calc_temp_decrease_K(self, time_slot: DateTime) -> float:
        pass

    @abstractmethod
    def _calc_temp_increase_K(self, time_slot: DateTime, traded_energy_kWh: float) -> float:
        pass

    def _calc_energy_demand(self, time_slot: DateTime):
        self.state.set_min_energy_demand_kWh(
            time_slot, self._calc_energy_to_buy_minimum(time_slot))
        self.state.set_max_energy_demand_kWh(
            time_slot, self._calc_energy_to_buy_maximum(time_slot))

    def event_traded_energy(self, time_slot: DateTime, energy_kWh: float):
        """React to an event_traded_energy."""
        self._decrement_posted_energy(time_slot, energy_kWh)

        self.state.update_temp_increase_K(
            time_slot, self._calc_temp_increase_K(time_slot, energy_kWh))

    def _decrement_posted_energy(self, time_slot: DateTime, energy_kWh: float):
        updated_min_energy_demand_kWh = max(
            0., self.get_min_energy_demand_kWh(time_slot) - energy_kWh)
        updated_max_energy_demand_kWh = max(
            0., self.get_max_energy_demand_kWh(time_slot) - energy_kWh)
        self.state.set_min_energy_demand_kWh(time_slot, updated_min_energy_demand_kWh)
        self.state.set_max_energy_demand_kWh(time_slot, updated_max_energy_demand_kWh)


class HeatPumpEnergyParameters(HeatPumpEnergyParametersBase):
    """Energy Parameters for the heat pump."""
    # pylint: disable=too-many-instance-attributes, too-many-arguments
    def __init__(
            self,
            maximum_power_rating_kW: float = ConstSettings.HeatPumpSettings.MAX_POWER_RATING_KW,
            min_temp_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C,
            max_temp_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C,
            initial_temp_C: float = ConstSettings.HeatPumpSettings.INIT_TEMP_C,
            external_temp_C_profile: Optional[Union[str, float, Dict]] = None,
            external_temp_C_profile_uuid: Optional[str] = None,
            tank_volume_l: float = ConstSettings.HeatPumpSettings.TANK_VOL_L,
            consumption_kWh_profile: Optional[Union[str, float, Dict]] = None,
            consumption_kWh_profile_uuid: Optional[str] = None,
            source_type: int = ConstSettings.HeatPumpSettings.SOURCE_TYPE):

        super().__init__(
            maximum_power_rating_kW, min_temp_C, max_temp_C, initial_temp_C, tank_volume_l)
        self._source_type = source_type

        self._consumption_kWh: [DateTime, float] = EnergyProfile(
            consumption_kWh_profile, consumption_kWh_profile_uuid,
            profile_type=InputProfileTypes.ENERGY_KWH)

        self._ext_temp_C: [DateTime, float] = EnergyProfile(
            external_temp_C_profile, external_temp_C_profile_uuid,
            profile_type=InputProfileTypes.IDENTITY)

    def serialize(self):
        """Return dict with the current energy parameter values."""
        return {
            **super().serialize(),
            "consumption_kWh": self._consumption_kWh.input_profile,
            "consumption_profile_uuid": self._consumption_kWh.input_profile_uuid,
            "external_temp_C": self._ext_temp_C.input_profile,
            "external_temp_profile_uuid": self._ext_temp_C.input_profile_uuid,
            "source_type": self._source_type,
        }

    def _temp_diff_to_Q_kWh(self, diff_temp_K: float) -> float:
        return diff_temp_K * self._Q_specific

    def _Q_kWh_to_temp_diff(self, energy_kWh: float) -> float:
        return energy_kWh / self._Q_specific

    def _rotate_profiles(self, current_time_slot: Optional[DateTime] = None):
        super()._rotate_profiles(current_time_slot)
        self._consumption_kWh.read_or_rotate_profiles()
        self._ext_temp_C.read_or_rotate_profiles()

    def _calc_energy_to_buy_maximum(self, time_slot: DateTime) -> float:
        max_energy_consumption = self._temp_diff_to_Q_kWh(
            self._max_temp_C -
            self.state.get_storage_temp_C(time_slot) +
            self.state.get_temp_decrease_K(time_slot)) / self.state.get_cop(time_slot)

        assert max_energy_consumption > -FLOATING_POINT_TOLERANCE
        if max_energy_consumption > self._max_energy_consumption_kWh:
            # demand is higher than max_power_rating
            self.state.update_unmatched_demand_kWh(
                time_slot, max_energy_consumption - self._max_energy_consumption_kWh)
            return self._max_energy_consumption_kWh
        return max_energy_consumption

    def _calc_energy_to_buy_minimum(self, time_slot: DateTime) -> float:
        max_temp_decrease_allowed = (
                self.state.get_storage_temp_C(time_slot) - self._min_temp_C)
        temp_diff = self.state.get_temp_decrease_K(time_slot)
        if abs(temp_diff - max_temp_decrease_allowed) < -FLOATING_POINT_TOLERANCE:
            return 0
        min_energy_consumption = (
                self._temp_diff_to_Q_kWh(temp_diff) / self.state.get_cop(time_slot))

        if min_energy_consumption > self._max_energy_consumption_kWh:
            print("min")
            # demand is higher than max_power_rating
            self.state.update_unmatched_demand_kWh(
                time_slot, min_energy_consumption - self._max_energy_consumption_kWh)
            return self._max_energy_consumption_kWh
        return min_energy_consumption

    def _calc_temp_decrease_K(self, time_slot: DateTime) -> float:
        demanded_temp_decrease_K = self._Q_kWh_to_temp_diff(self._calc_Q_from_energy_kWh(
            time_slot, self._consumption_kWh.profile[time_slot]))
        if self.state.get_storage_temp_C(time_slot) - demanded_temp_decrease_K < self._min_temp_C:
            actual_temp_decrease = self.state.get_storage_temp_C(time_slot) - self._min_temp_C
            unmatched_demand_kWh = self._temp_diff_to_Q_kWh(
                demanded_temp_decrease_K - actual_temp_decrease) / self.state.get_cop(time_slot)
            self.state.update_unmatched_demand_kWh(time_slot, unmatched_demand_kWh)
        else:
            actual_temp_decrease = demanded_temp_decrease_K

        return actual_temp_decrease

    def _calc_temp_increase_K(self, time_slot: DateTime, traded_energy_kWh: float) -> float:
        self.state.update_unmatched_demand_kWh(time_slot, -traded_energy_kWh)
        return self._Q_kWh_to_temp_diff(self._calc_Q_from_energy_kWh(time_slot, traded_energy_kWh))

    def _populate_state(self, time_slot: DateTime):
        super()._populate_state(time_slot)
        self.state.set_energy_consumption_kWh(time_slot, self._consumption_kWh.profile[time_slot])

    def _calc_Q_from_energy_kWh(self, time_slot: DateTime, energy_kWh: float) -> float:
        return self.state.get_cop(time_slot) * energy_kWh

    def _calc_cop(self, time_slot: DateTime) -> float:
        """
        Return the coefficient of performance (COP) for a given ambient and storage temperature.
        The COP of a heat pump depends on various parameters, but can be modeled using
        the two temperatures.
        Generally, the higher the temperature difference between the source and the sink,
        the lower the efficiency of the heat pump (the lower COP).
        """
        return self._cop_model(self.state.get_storage_temp_C(time_slot),
                               self._ext_temp_C.profile[time_slot])

    def _cop_model(self, temp_current: float, temp_ambient: float) -> float:
        """COP model following https://www.nature.com/articles/s41597-019-0199-y"""
        delta_temp = temp_current - temp_ambient
        if self._source_type == HeatPumpSourceType.AIR.value:
            return 6.08 - 0.09 * delta_temp + 0.0005 * delta_temp**2
        if self._source_type == HeatPumpSourceType.GROUND.value:
            return 10.29 - 0.21 * delta_temp + 0.0012 * delta_temp**2

        raise HeatPumpEnergyParametersException("HeatPumpSourceType not supported")
