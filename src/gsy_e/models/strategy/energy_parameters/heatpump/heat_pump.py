from abc import ABC, abstractmethod
from typing import Optional, Dict, Union, List

from gsy_framework.constants_limits import ConstSettings, GlobalConfig, FLOATING_POINT_TOLERANCE
from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.utils import convert_kJ_to_kWh, convert_kWh_to_kJ
from pendulum import DateTime

from gsy_e.models.strategy.energy_parameters.heatpump.cop_models import (
    COPModelType,
    cop_model_factory,
)
from gsy_e.models.strategy.energy_parameters.heatpump.tank import (
    TankParameters,
    AllTanksEnergyParameters,
)
from gsy_e.models.strategy.state import HeatPumpState
from gsy_e.models.strategy.strategy_profile import profile_factory

# pylint: disable=pointless-string-statement
"""
Description of physical units and parameters:
- K .. Kelvin:              Si unit, used for temperature differences
- C .. degrees celsius:     Used for temperatures
- Q .. heat/thermal energy: Energy that a body has or needs to have/get a certain temperature [kWh]
"""


class HeatPumpEnergyParametersException(Exception):
    """Exception raised in the HeatPumpEnergyParameters"""


class CombinedHeatpumpTanksState:
    """Combined state that includes both heatpump and tanks state."""

    def __init__(self, hp_state: HeatPumpState, tanks_state: AllTanksEnergyParameters):
        self._hp_state = hp_state
        self._tanks_state = tanks_state

    def get_results_dict(self, current_time_slot: DateTime) -> dict:
        """Results dict for all heatpump and tanks results."""
        tanks_state = self._tanks_state.get_results_dict(current_time_slot)
        if isinstance(tanks_state, list):
            return {
                "tanks": tanks_state,
                **self._hp_state.get_results_dict(current_time_slot),
            }
        return {**self._hp_state.get_results_dict(current_time_slot), **tanks_state}

    def get_state(self) -> Dict:
        """Return the current state of the device."""
        return {
            **self._hp_state.get_state(),
            "tanks": self._tanks_state.get_state(),
        }

    def restore_state(self, state_dict: Dict):
        """Update the state of the device using the provided dictionary."""
        self._hp_state.restore_state(state_dict)
        self._tanks_state.restore_state(state_dict)

    def delete_past_state_values(self, current_time_slot: DateTime):
        """Delete the state of the device before the given time slot."""
        self._hp_state.delete_past_state_values(current_time_slot)
        self._tanks_state.delete_past_state_values(current_time_slot)

    @property
    def heatpump(self) -> HeatPumpState:
        """Exposes the heatpump state."""
        return self._hp_state

    @property
    def tanks(self) -> AllTanksEnergyParameters:
        """Exposes the tanks state."""
        return self._tanks_state


class HeatPumpEnergyParametersBase(ABC):
    """
    Base class for common functionality across all heatpump strategies / models that include heat
    storage. Does not depend on a specific heatpump model, and cannot be instantiated on its own.
    """

    # pylint: disable=too-many-arguments, too-many-instance-attributes
    def __init__(
        self,
        maximum_power_rating_kW: float = ConstSettings.HeatPumpSettings.MAX_POWER_RATING_KW,
        tank_parameters: List[TankParameters] = None,
    ):
        self._slot_length = GlobalConfig.slot_length
        self._maximum_power_rating_kW = maximum_power_rating_kW
        self._max_energy_consumption_kWh = (
            maximum_power_rating_kW * self._slot_length.total_hours()
        )
        state = HeatPumpState(self._slot_length)
        tanks = AllTanksEnergyParameters(tank_parameters)
        self._state = CombinedHeatpumpTanksState(state, tanks)

    @property
    def combined_state(self) -> CombinedHeatpumpTanksState:
        """Combined heatpump and tanks state."""
        return self._state

    def last_time_slot(self, current_market_slot: DateTime) -> DateTime:
        """Calculate the previous time slot from the current one."""
        return current_market_slot - self._slot_length

    def event_activate(self):
        """Runs on activate event."""
        self._rotate_profiles()

    def event_market_cycle(self, current_time_slot):
        """To be called at the start of the market slot."""
        self._rotate_profiles(current_time_slot)
        self._populate_state(current_time_slot)

    def get_min_energy_demand_kWh(self, time_slot: DateTime) -> float:
        """Get energy that is needed to compensate for the heat los due to heating."""
        return self._state.heatpump.get_min_energy_demand_kWh(time_slot)

    def get_max_energy_demand_kWh(self, time_slot: DateTime) -> float:
        """Get energy that is needed to heat up the storage to temp_max."""
        return self._state.heatpump.get_max_energy_demand_kWh(time_slot)

    @abstractmethod
    def _rotate_profiles(self, current_time_slot: Optional[DateTime] = None):
        self._state.heatpump.delete_past_state_values(current_time_slot)

    def _populate_state(self, time_slot: DateTime):
        self._calc_energy_demand(time_slot)
        self._calculate_and_set_unmatched_demand(time_slot)

    def _calculate_and_set_unmatched_demand(self, time_slot: DateTime):
        pass

    def _calc_cop(self, time_slot: DateTime) -> float:
        pass

    @abstractmethod
    def _calc_energy_to_buy_maximum(self, time_slot: DateTime) -> float:
        pass

    @abstractmethod
    def _calc_energy_to_buy_minimum(self, time_slot: DateTime) -> float:
        pass

    def _calc_energy_demand(self, time_slot: DateTime):
        self._state.heatpump.set_min_energy_demand_kWh(
            time_slot, self._calc_energy_to_buy_minimum(time_slot)
        )
        self._state.heatpump.set_max_energy_demand_kWh(
            time_slot, self._calc_energy_to_buy_maximum(time_slot)
        )

    def _decrement_posted_energy(self, time_slot: DateTime, energy_kWh: float):
        updated_min_energy_demand_kWh = max(
            0.0, self.get_min_energy_demand_kWh(time_slot) - energy_kWh
        )
        updated_max_energy_demand_kWh = max(
            0.0, self.get_max_energy_demand_kWh(time_slot) - energy_kWh
        )
        self._state.heatpump.set_min_energy_demand_kWh(time_slot, updated_min_energy_demand_kWh)
        self._state.heatpump.set_max_energy_demand_kWh(time_slot, updated_max_energy_demand_kWh)
        self._state.heatpump.increase_total_traded_energy_kWh(energy_kWh)


class HeatPumpEnergyParameters(HeatPumpEnergyParametersBase):
    """Energy Parameters for the heat pump."""

    # pylint: disable=too-many-instance-attributes, too-many-arguments
    def __init__(
        self,
        maximum_power_rating_kW: float = ConstSettings.HeatPumpSettings.MAX_POWER_RATING_KW,
        tank_parameters: List[TankParameters] = None,
        source_temp_C_profile: Optional[Union[str, float, Dict]] = None,
        source_temp_C_profile_uuid: Optional[str] = None,
        source_temp_C_measurement_uuid: Optional[str] = None,
        consumption_kWh_profile: Optional[Union[str, float, Dict]] = None,
        consumption_kWh_profile_uuid: Optional[str] = None,
        consumption_kWh_measurement_uuid: Optional[str] = None,
        source_type: int = ConstSettings.HeatPumpSettings.SOURCE_TYPE,
        heat_demand_Q_profile: Optional[Union[str, float, Dict]] = None,
        cop_model_type: COPModelType = COPModelType.UNIVERSAL,
    ):

        super().__init__(maximum_power_rating_kW, tank_parameters)

        self._source_type = source_type

        self._consumption_kWh: [DateTime, float] = profile_factory(
            consumption_kWh_profile,
            consumption_kWh_profile_uuid,
            profile_type=InputProfileTypes.ENERGY_KWH,
        )

        if heat_demand_Q_profile:
            self._heat_demand_Q_J: [DateTime, float] = profile_factory(
                heat_demand_Q_profile, None, profile_type=InputProfileTypes.IDENTITY
            )
        else:
            self._heat_demand_Q_J = None

        self._source_temp_C: [DateTime, float] = profile_factory(
            source_temp_C_profile,
            source_temp_C_profile_uuid,
            profile_type=InputProfileTypes.IDENTITY,
        )

        self._measurement_consumption_kWh: [DateTime, float] = profile_factory(
            None, consumption_kWh_measurement_uuid, profile_type=InputProfileTypes.ENERGY_KWH
        )

        self._measurement_source_temp_C: [DateTime, float] = profile_factory(
            None, source_temp_C_measurement_uuid, profile_type=InputProfileTypes.IDENTITY
        )

        self._cop_model = cop_model_factory(cop_model_type, source_type)

    def serialize(self):
        """Return dict with the current energy parameter values."""
        return {
            "tanks": self._state.tanks.serialize(),
            "max_energy_consumption_kWh": self._max_energy_consumption_kWh,
            "maximum_power_rating_kW": self._maximum_power_rating_kW,
            "consumption_kWh": self._consumption_kWh.input_profile,
            "consumption_profile_uuid": self._consumption_kWh.input_profile_uuid,
            "consumption_kWh_measurement_uuid": (
                self._measurement_consumption_kWh.input_profile_uuid
            ),
            "source_temp_C": self._source_temp_C.input_profile,
            "source": self._source_temp_C.input_profile_uuid,
            "source_temp_measurement_uuid": self._measurement_source_temp_C.input_profile_uuid,
            "source_type": self._source_type,
        }

    def event_traded_energy(self, time_slot: DateTime, energy_kWh: float):
        """React to an event_traded_energy."""
        self._decrement_posted_energy(time_slot, energy_kWh)

        traded_heat_energy_kJ = self._calc_Q_kJ_from_energy_kWh(time_slot, energy_kWh)
        self._state.tanks.increase_tanks_temp_from_heat_energy(traded_heat_energy_kJ, time_slot)

        self._calculate_and_set_unmatched_demand(time_slot)

    def _rotate_profiles(self, current_time_slot: Optional[DateTime] = None):
        super()._rotate_profiles(current_time_slot)
        self._consumption_kWh.read_or_rotate_profiles()
        self._source_temp_C.read_or_rotate_profiles()
        if self._heat_demand_Q_J:
            self._heat_demand_Q_J.read_or_rotate_profiles()

    def _calc_energy_to_buy_maximum(self, time_slot: DateTime) -> float:
        cop = self._state.heatpump.get_cop(time_slot)
        if cop == 0:
            return 0
        max_energy_consumption_kWh = self._state.tanks.get_max_energy_consumption(cop, time_slot)
        assert max_energy_consumption_kWh > -FLOATING_POINT_TOLERANCE
        if max_energy_consumption_kWh > self._max_energy_consumption_kWh:
            return self._max_energy_consumption_kWh
        return max_energy_consumption_kWh

    def _calc_energy_to_buy_minimum(self, time_slot: DateTime) -> float:
        cop = self._state.heatpump.get_cop(time_slot)
        if cop == 0:
            return 0
        min_energy_consumption_kWh = self._state.tanks.get_min_energy_consumption(cop, time_slot)
        if min_energy_consumption_kWh > self._max_energy_consumption_kWh:
            return self._max_energy_consumption_kWh
        return min_energy_consumption_kWh

    def _populate_state(self, time_slot: DateTime):
        self._state.tanks.update_tanks_temperature(time_slot)
        self._state.heatpump.set_cop(time_slot, self._calc_cop(time_slot))

        if not self._heat_demand_Q_J:
            produced_heat_energy_kJ = self._calc_Q_kJ_from_energy_kWh(
                time_slot, self._consumption_kWh.profile[time_slot]
            )
        else:
            produced_heat_energy_kJ = self._heat_demand_Q_J.get_value(time_slot) / 1000.0
            energy_demand_kWh = self._calc_energy_kWh_from_Q_kJ(time_slot, produced_heat_energy_kJ)
            self._consumption_kWh.profile[time_slot] = energy_demand_kWh

        self._state.heatpump.set_heat_demand(time_slot, produced_heat_energy_kJ * 1000)
        self._state.tanks.decrease_tanks_temp_from_heat_energy(produced_heat_energy_kJ, time_slot)
        super()._populate_state(time_slot)
        self._state.heatpump.set_energy_consumption_kWh(
            time_slot, self._consumption_kWh.get_value(time_slot)
        )

    def _calc_Q_kJ_from_energy_kWh(self, time_slot: DateTime, energy_kWh: float) -> float:
        return convert_kWh_to_kJ(self._state.heatpump.get_cop(time_slot) * energy_kWh)

    def _calc_energy_kWh_from_Q_kJ(self, time_slot: DateTime, Q_energy_kJ: float) -> float:
        cop = self._state.heatpump.get_cop(time_slot)
        if cop == 0:
            return 0
        return convert_kJ_to_kWh(Q_energy_kJ / self._state.heatpump.get_cop(time_slot))

    def _calc_cop(self, time_slot: DateTime) -> float:
        """
        Return the coefficient of performance (COP) for a given ambient and storage temperature.
        The COP of a heat pump depends on various parameters, but can be modeled using
        the two temperatures.
        Generally, the higher the temperature difference between the source and the sink,
        the lower the efficiency of the heat pump (the lower COP).
        """
        # 1 J = 1 W s
        heat_demand_kW = (
            self._heat_demand_Q_J.get_value(time_slot) / self._slot_length.total_seconds() / 1000
            if self._heat_demand_Q_J
            else None
        )
        return self._cop_model.calc_cop(
            source_temp_C=self._source_temp_C.get_value(time_slot),
            tank_temp_C=self._state.tanks.get_average_tank_temperature(time_slot),
            heat_demand_kW=heat_demand_kW,
        )

    def _calculate_and_set_unmatched_demand(self, time_slot: DateTime) -> None:
        unmatched_energy_demand = self._state.tanks.get_unmatched_demand_kWh(time_slot)
        if unmatched_energy_demand < FLOATING_POINT_TOLERANCE:
            self._state.heatpump.set_unmatched_demand_kWh(time_slot, unmatched_energy_demand)
