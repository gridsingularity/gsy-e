from typing import Dict, Union, Optional

from gsy_framework.constants_limits import ConstSettings, GlobalConfig, FLOATING_POINT_TOLERANCE
from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.utils import (
    convert_kWh_to_W,
    convert_W_to_kWh,
    convert_kJ_to_kWh,
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
from gsy_e.models.strategy.energy_parameters.heatpump.pcm_tank_model.pcm_model_utils_constants import (
    MASS_FLOW_RATE,
)
from gsy_e.models.strategy.energy_parameters.heatpump.tank_parameters import TankParameters
from gsy_e.models.strategy.state import HeatPumpState
from gsy_e.models.strategy.state.heatpump_pcm_tank_state import PCMTankState
from gsy_e.models.strategy.strategy_profile import profile_factory


# todo: remove whole module


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
        tank_parameters: TankParameters = None,
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
            max_capacity_kWh=tank_parameters.max_capacity_kJ,
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

    def event_activate(self):
        self._state.tank.init_storage_temps()
        super().event_activate()

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
            self._increase_tank_temp_from_heat_energy(
                consumed_heat_kWh - heat_demand_kWh, last_time_slot
            )
        elif heat_demand_kWh > 0:
            self._decrease_tank_temp_from_heat_energy(
                heat_demand_kWh - consumed_heat_kWh, last_time_slot
            )

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
        self._state.tank._increase_storage_temp_from_condensor_temp(temp_cond_C, time_slot)

    def _decrease_tank_temp_from_heat_energy(self, heat_energy_kWh: float, time_slot: DateTime):
        temp_cond_C = self._get_condensor_temp_from_heat_demand_kWh(-heat_energy_kWh, time_slot)
        self._state.tank._decrease_storage_temp_from_condensor_temp(temp_cond_C, time_slot)

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
        maximum_soc_energy_kWh = self._state.tank._get_maximum_available_storage_energy_kWh(
            time_slot
        )
        maximum_heat_energy_kWh = min(
            self._max_energy_consumption_kWh, maximum_heat_demand_kWh, maximum_soc_energy_kWh
        )
        return maximum_heat_energy_kWh / self._state.heatpump.get_cop(time_slot)

    def _calc_energy_to_buy_minimum(self, time_slot: DateTime) -> float:
        available_soc_kWh = self._state.tank._get_maximum_available_storage_energy_kWh(time_slot)
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
