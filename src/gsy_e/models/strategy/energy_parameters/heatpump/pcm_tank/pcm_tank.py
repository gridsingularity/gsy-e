from collections import defaultdict
import logging
from dataclasses import dataclass
from statistics import mean
from typing import Dict, Union, Optional

from gsy_framework.constants_limits import ConstSettings, GlobalConfig, FLOATING_POINT_TOLERANCE
from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.utils import (
    convert_kWh_to_W,
    convert_W_to_kWh,
    convert_kJ_to_kWh,
    convert_pendulum_to_str_in_dict,
    convert_str_to_pendulum_in_dict,
)
from pendulum import DateTime

from gsy_e.models.strategy.energy_parameters.heatpump.constants import SPECIFIC_HEAT_CAPACITY_WATER
from gsy_e.models.strategy.energy_parameters.heatpump.cop_models import (
    COPModelType,
    cop_model_factory,
)
from gsy_e.models.strategy.energy_parameters.heatpump.heat_pump import (
    HeatPumpEnergyParameters,
)
from gsy_e.models.strategy.energy_parameters.heatpump.pcm_tank.pcm_models import (
    PCMDischargeModel,
    PCMChargeModel,
)
from gsy_e.models.strategy.energy_parameters.heatpump.pcm_tank.pcm_model_utils_constants import (
    MASS_FLOW_RATE,
    NUMBER_OF_PCM_ELEMENTS,
)
from gsy_e.models.strategy.state import HeatPumpState
from gsy_e.models.strategy.state.heat_pump_state import delete_time_slots_in_state
from gsy_e.models.strategy.state.base_states import StateInterface
from gsy_e.models.strategy.strategy_profile import profile_factory
from gsy_e import constants

log = logging.getLogger()


@dataclass
class PCMTankParameters:
    """Nameplate parameters of a water tank."""

    min_temp_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C
    max_temp_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C
    initial_temp_C: float = ConstSettings.HeatPumpSettings.INIT_TEMP_C
    max_capacity_kWh: float = 6.0  # todo: put default value somewhere


class PCMTankState(StateInterface):
    """State class for the PCM tank"""

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        initial_temp_C: float,
        min_storage_temp_C: float,
        max_storage_temp_C: float,
        max_capacity_kWh: float,
    ):
        self._storage_temp_C: Dict[DateTime, list[float]] = {}
        self._initial_temp_C = initial_temp_C
        self._consumed_energy: Dict[DateTime, float] = defaultdict(lambda: 0)
        self.min_storage_temp_C = min_storage_temp_C
        self.max_storage_temp_C = max_storage_temp_C
        self._soc: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._max_capacity_kWh = max_capacity_kWh
        self._pcm_charge_model = PCMChargeModel(
            slot_length=GlobalConfig.slot_length, mass_flow_rate_kg_s=MASS_FLOW_RATE
        )
        self._pcm_discharge_model = PCMDischargeModel(
            slot_length=GlobalConfig.slot_length, mass_flow_rate_kg_s=MASS_FLOW_RATE
        )

    def serialize(self):
        """Return serializable dict of class parameters."""
        return {
            "initial_temp_C": self._initial_temp_C,
            "min_storage_temp_C": self.min_storage_temp_C,
            "max_storage_temp_C": self.max_storage_temp_C,
            "max_capacity_kWh": self._max_capacity_kWh,
        }

    def update_consumed_energy(self, energy: float, time_slot: DateTime) -> None:
        """Add provided energy value to the value in consumed_energy for the provided time_slot."""
        self._consumed_energy[time_slot] = self._consumed_energy.get(time_slot, 0.0) + energy

    def get_consumed_energy(self, time_slot: DateTime):
        """Return consumed_energy for the provided time_slot"""
        return self._consumed_energy.get(time_slot, 0.0)

    def init_storage_temps(self):
        """
        Initiate the storage temperatures with the initial temperature of the storge
        """
        self._storage_temp_C[GlobalConfig.start_date] = [
            self._initial_temp_C for _ in range(NUMBER_OF_PCM_ELEMENTS)
        ]

    def is_time_slot_available(self, time_slot: DateTime) -> bool:
        """Return True if the provided time_slot is part of the _storage_temp_C dict."""
        return time_slot in self._storage_temp_C

    def get_storage_temp_C(self, time_slot: DateTime) -> Optional[list]:
        """Get storage_temp_C for specific time_slot."""
        return self._storage_temp_C.get(time_slot, None)

    def set_soc_after_charging(self, time_slot: DateTime):
        """Calculate and set SOC level after charging."""
        self._soc[time_slot] = self._pcm_charge_model.get_soc(self._storage_temp_C[time_slot])

    def set_soc_after_discharging(self, time_slot: DateTime):
        """Calculate and set SOC level after discharging."""
        self._soc[time_slot] = self._pcm_discharge_model.get_soc(self._storage_temp_C[time_slot])

    def get_soc(self, time_slot: DateTime) -> float:
        """Return SOC level."""
        return self._soc[time_slot]

    def get_htf_temp_C(self, time_slot: DateTime) -> Optional[float]:
        """Return mean temperature of the heat transfer fluid"""
        storage_temps = self.get_storage_temp_C(time_slot)
        if storage_temps is None:
            return None
        return mean(storage_temps[0:-2:2])

    def get_pcm_temp_C(self, time_slot: DateTime) -> Optional[float]:
        """Return the mean temperature of the PCM."""
        storage_temps = self.get_storage_temp_C(time_slot)
        if storage_temps is None:
            return None
        return mean(storage_temps[1:-1:2])

    def get_maximum_available_storage_energy_kWh(self, time_slot: DateTime):
        """Return the maximum available energy that can be stored in the storage."""
        return self._max_capacity_kWh - self.get_soc(time_slot) * self._max_capacity_kWh

    def _is_temp_limit_respected(self, condensor_temp_C: float) -> bool:
        if (
            condensor_temp_C < self.min_storage_temp_C
            or condensor_temp_C > self.max_storage_temp_C
        ):
            log.error(
                "The PCM storage tank reach it's maximum, charging /discharging "
                "condensor temperature of %s is omitted",
                condensor_temp_C,
            )
            return False
        return True

    def increase_storage_temp_from_condensor_temp(
        self, condensor_temp_C: float, time_slot: DateTime
    ):
        """Increase storage temperatures for provided condensor temperature."""
        if not self._is_temp_limit_respected(condensor_temp_C):
            self._storage_temp_C[time_slot + GlobalConfig.slot_length] = self.get_storage_temp_C(
                time_slot
            )
            return
        temperatures_after_charging = self._pcm_charge_model.get_temp_after_charging(
            current_storage_temps=self.get_storage_temp_C(time_slot),
            charging_temp=condensor_temp_C,
        )
        self._storage_temp_C[time_slot + GlobalConfig.slot_length] = temperatures_after_charging

    def decrease_storage_temp_from_condensor_temp(
        self, condensor_temp_C: float, time_slot: DateTime
    ):
        """Decrease storage temperatures for provided condensor temperature."""
        if not self._is_temp_limit_respected(condensor_temp_C):
            self._storage_temp_C[time_slot + GlobalConfig.slot_length] = self.get_storage_temp_C(
                time_slot
            )
            return
        temperatures_after_discharging = self._pcm_discharge_model.get_temp_after_discharging(
            current_storage_temps=self.get_storage_temp_C(time_slot),
            discharging_temp=condensor_temp_C,
        )
        self._storage_temp_C[time_slot + GlobalConfig.slot_length] = temperatures_after_discharging

    def get_results_dict(self, current_time_slot: DateTime) -> dict:
        return {
            "storage_temp_C": self._storage_temp_C.get(current_time_slot, []),
            "consumed_energy": self._consumed_energy.get(current_time_slot, 0),
            "soc": self._soc.get(current_time_slot, 0),
            "htf_temp_C": self.get_htf_temp_C(current_time_slot),
            "pcm_temp_C": self.get_pcm_temp_C(current_time_slot),
        }

    def get_state(self) -> Dict:
        return {
            "storage_temp_C": convert_pendulum_to_str_in_dict(self._storage_temp_C),
            "consumed_energy": convert_pendulum_to_str_in_dict(self._consumed_energy),
            "soc": convert_pendulum_to_str_in_dict(self._soc),
            "min_storage_temp_C": self.min_storage_temp_C,
            "max_storage_temp_C": self.max_storage_temp_C,
            "max_capacity_kWh": self._max_capacity_kWh,
            "initial_temp_C": self._initial_temp_C,
        }

    def restore_state(self, state_dict: Dict):
        self._storage_temp_C = convert_str_to_pendulum_in_dict(state_dict["storage_temp_C"])
        self._consumed_energy = convert_str_to_pendulum_in_dict(state_dict["consumed_energy"])
        self._soc = convert_str_to_pendulum_in_dict(state_dict["soc"])
        self.min_storage_temp_C = state_dict["min_storage_temp_C"]
        self.max_storage_temp_C = state_dict["max_storage_temp_C"]
        self._max_capacity_kWh = state_dict["max_capacity_kWh"]
        self._initial_temp_C = state_dict["initial_temp_C"]

    def delete_past_state_values(self, current_time_slot: DateTime):
        if not current_time_slot or constants.RETAIN_PAST_MARKET_STRATEGIES_STATE:
            return
        last_time_slot = self._last_time_slot(current_time_slot)
        delete_time_slots_in_state(self._storage_temp_C, last_time_slot)
        delete_time_slots_in_state(self._soc, last_time_slot)
        delete_time_slots_in_state(self._consumed_energy, last_time_slot)

    def _last_time_slot(self, current_market_slot: DateTime) -> DateTime:
        return current_market_slot - GlobalConfig.slot_length


class CombinedHeatpumpPCMTankState:
    """State class that combines states of heat pump and tank"""

    def __init__(self, hp_state: HeatPumpState, tanks_state: PCMTankState):
        self._hp_state = hp_state
        self._tank_state = tanks_state

    def get_results_dict(self, current_time_slot: DateTime) -> dict:
        """Results dict for all heatpump and tanks results."""
        return {
            **self._tank_state.get_results_dict(current_time_slot),
            **self._hp_state.get_results_dict(current_time_slot),
        }

    def get_state(self) -> Dict:
        """Return the current state of the device."""
        return {
            **self._hp_state.get_state(),
            "tank": self._tank_state.get_state(),
        }

    def restore_state(self, state_dict: Dict):
        """Update the state of the device using the provided dictionary."""
        self._hp_state.restore_state(state_dict)
        self._tank_state.restore_state(state_dict)

    def delete_past_state_values(self, current_time_slot: DateTime):
        """Delete the state of the device before the given time slot."""
        self._hp_state.delete_past_state_values(current_time_slot)
        self._tank_state.delete_past_state_values(current_time_slot)

    @property
    def heatpump(self) -> HeatPumpState:
        """Exposes the heatpump state."""
        return self._hp_state

    @property
    def tank(self) -> PCMTankState:
        """Exposes the tank state."""
        return self._tank_state


class PCMHeatPumpEnergyParameters(HeatPumpEnergyParameters):
    """Class for energy parameters of the PCM heat Pump"""

    # pylint: disable=too-many-instance-attributes, too-many-arguments

    def __init__(
        self,
        maximum_power_rating_kW: float = ConstSettings.HeatPumpSettings.MAX_POWER_RATING_KW,
        tank_parameters: PCMTankParameters = None,
        source_temp_C_profile: Optional[Union[str, float, Dict]] = None,
        source_temp_C_profile_uuid: Optional[str] = None,
        source_temp_C_measurement_uuid: Optional[str] = None,
        consumption_kWh_profile: Optional[Union[str, float, Dict]] = None,
        consumption_kWh_profile_uuid: Optional[str] = None,
        consumption_kWh_measurement_uuid: Optional[str] = None,
        source_type: int = ConstSettings.HeatPumpSettings.SOURCE_TYPE,
        heat_demand_Q_profile: Optional[Union[str, float, Dict]] = None,
        cop_model_type: COPModelType = COPModelType.UNIVERSAL,
    ):  # pylint: disable=super-init-not-called)

        hp_state = HeatPumpState(GlobalConfig.slot_length)
        tank_state = PCMTankState(
            initial_temp_C=tank_parameters.initial_temp_C,
            min_storage_temp_C=tank_parameters.min_temp_C,
            max_storage_temp_C=tank_parameters.max_temp_C,
            max_capacity_kWh=tank_parameters.max_capacity_kWh,
        )

        self._state = CombinedHeatpumpPCMTankState(hp_state, tank_state)

        self._maximum_power_rating_kW = maximum_power_rating_kW
        self._max_energy_consumption_kWh = (
            maximum_power_rating_kW * GlobalConfig.slot_length.total_hours()
        )

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
        self._cop_model_type = cop_model_type
        self._cop_model = cop_model_factory(cop_model_type, source_type)
        self._slot_length = GlobalConfig.slot_length

    def serialize(self):
        return {
            "tank": self._state.tank.serialize(),
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
            "cop_model": self._cop_model_type.value,
        }

    @property
    def combined_state(self) -> CombinedHeatpumpPCMTankState:
        """Combined heatpump and tanks state."""
        return self._state

    def event_activate(self):
        self._state.tank.init_storage_temps()

    def event_traded_energy(self, time_slot: DateTime, energy_kWh: float):
        """React to an event_traded_energy."""
        self._decrement_posted_energy(time_slot, energy_kWh)
        self._state.tank.update_consumed_energy(energy_kWh, time_slot)
        self._calculate_and_set_unmatched_demand(time_slot)

    def _populate_state(self, time_slot: DateTime):
        # Order matters a lot here!
        # Adapt the storage temps according to the trading in the last market slot:
        self._adapt_storage_temps(time_slot)

        self._state.heatpump.set_cop(time_slot, self._calc_cop(time_slot))

        if not self._heat_demand_Q_J:
            produced_heat_energy_kJ = self._calc_Q_kJ_from_energy_kWh(
                time_slot, self._consumption_kWh.get_value(time_slot)
            )
        else:
            produced_heat_energy_kJ = self._heat_demand_Q_J.get_value(time_slot) / 1000.0

        self._state.heatpump.set_heat_demand(time_slot, produced_heat_energy_kJ * 1000)

        self._calc_energy_demand(time_slot)

        self._calculate_and_set_unmatched_demand(time_slot)

    def _adapt_storage_temps(self, time_slot: DateTime):
        last_time_slot = self.last_time_slot(time_slot)
        if not self._state.tank.is_time_slot_available(last_time_slot):
            return
        heat_demand_kWh = self._get_heat_demand_kWh(last_time_slot)
        consumed_heat_kWh = self._get_consumed_heat_kWh(last_time_slot)
        if consumed_heat_kWh >= heat_demand_kWh:
            self._increase_tank_temp_from_heat_energy(consumed_heat_kWh, last_time_slot)
        elif heat_demand_kWh > 0:
            self._decrease_tank_temp_from_heat_energy(heat_demand_kWh, last_time_slot)

    def _get_consumed_heat_kWh(self, time_slot: DateTime) -> float:
        return self._state.tank.get_consumed_energy(time_slot) * self._state.heatpump.get_cop(
            time_slot
        )

    def _calculate_and_set_unmatched_demand(self, time_slot: DateTime) -> None:
        unmatched_energy_demand_kWh = self._get_consumed_heat_kWh(
            time_slot
        ) - self._get_heat_demand_kWh(time_slot)
        if unmatched_energy_demand_kWh < FLOATING_POINT_TOLERANCE:
            self._state.heatpump.set_unmatched_demand_kWh(
                time_slot, abs(unmatched_energy_demand_kWh)
            )

    def _get_deltaT_from_heat_demand_kWh(self, heat_energy_kWh: float) -> float:
        """
        Q > 0 --> dT >0
        Q < 0 --> dT <0
        """
        return convert_kWh_to_W(heat_energy_kWh, GlobalConfig.slot_length) / (
            MASS_FLOW_RATE * SPECIFIC_HEAT_CAPACITY_WATER
        )

    def _get_heat_demand_kWh_from_deltaT(self, deltaT: float) -> float:
        return convert_W_to_kWh(
            MASS_FLOW_RATE * SPECIFIC_HEAT_CAPACITY_WATER * deltaT, GlobalConfig.slot_length
        )

    def _get_condensor_temp_from_heat_demand_kWh(
        self, heat_energy_kWh: float, time_slot: DateTime
    ):
        condensor_temp_C = self._state.tank.get_htf_temp_C(
            time_slot
        ) + self._get_deltaT_from_heat_demand_kWh(heat_energy_kWh)
        assert 0 < condensor_temp_C < 100, f"unrealistic condensor temp {condensor_temp_C}"
        return condensor_temp_C

    def _increase_tank_temp_from_heat_energy(self, heat_energy_kWh: float, time_slot: DateTime):
        temp_cond_C = self._get_condensor_temp_from_heat_demand_kWh(heat_energy_kWh, time_slot)
        self._state.tank.increase_storage_temp_from_condensor_temp(temp_cond_C, time_slot)

    def _decrease_tank_temp_from_heat_energy(self, heat_energy_kWh: float, time_slot: DateTime):
        temp_cond_C = self._get_condensor_temp_from_heat_demand_kWh(-heat_energy_kWh, time_slot)
        self._state.tank.decrease_storage_temp_from_condensor_temp(temp_cond_C, time_slot)

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
            tank_temp_C=self._state.tank.get_htf_temp_C(time_slot),
            heat_demand_kW=heat_demand_kW,
        )

    def _calc_energy_demand(self, time_slot: DateTime):
        self._state.heatpump.set_min_energy_demand_kWh(
            time_slot, self._calc_energy_to_buy_minimum(time_slot)
        )
        self._state.heatpump.set_max_energy_demand_kWh(
            time_slot, self._calc_energy_to_buy_maximum(time_slot)
        )

    def _calc_energy_to_buy_maximum(self, time_slot: DateTime) -> float:
        deltaT = self._state.tank.max_storage_temp_C - self._state.tank.get_htf_temp_C(time_slot)
        assert deltaT > 0, (
            f"the tank temperature already exceeded its limit "
            f"{self._state.tank.get_htf_temp_C(time_slot)}"
        )

        maximum_heat_demand_kWh = self._get_heat_demand_kWh_from_deltaT(deltaT)
        maximum_soc_energy_kWh = self._state.tank.get_maximum_available_storage_energy_kWh(
            time_slot
        )
        maximum_heat_energy_kWh = min(
            self._max_energy_consumption_kWh, maximum_heat_demand_kWh, maximum_soc_energy_kWh
        )
        return maximum_heat_energy_kWh / self._state.heatpump.get_cop(time_slot)

    def _calc_energy_to_buy_minimum(self, time_slot: DateTime) -> float:
        available_soc_kWh = self._state.tank.get_maximum_available_storage_energy_kWh(time_slot)
        heat_demand_kWh = self._get_heat_demand_kWh(time_slot)
        energy_to_buy_minimum = (
            heat_demand_kWh if available_soc_kWh > heat_demand_kWh else available_soc_kWh
        )

        return min(
            self._max_energy_consumption_kWh,
            energy_to_buy_minimum / self._state.heatpump.get_cop(time_slot),
        )

    def _get_heat_demand_kWh(self, time_slot: DateTime):
        return convert_kJ_to_kWh(self._state.heatpump.get_heat_demand(time_slot) / 1000)
