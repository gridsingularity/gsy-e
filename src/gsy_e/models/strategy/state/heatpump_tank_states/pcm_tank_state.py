import logging
from statistics import mean
from typing import Dict, Optional

from pendulum import DateTime

from gsy_framework.constants_limits import GlobalConfig, FLOATING_POINT_TOLERANCE
from gsy_framework.utils import (
    convert_pendulum_to_str_in_dict,
    convert_str_to_pendulum_in_dict,
    convert_kWh_to_W,
)

from gsy_e import constants
from gsy_e.models.strategy.energy_parameters.heatpump.constants import SPECIFIC_HEAT_CAPACITY_WATER
from gsy_e.models.strategy.energy_parameters.heatpump.pcm_tank_model.pcm_models import (
    PCMDischargeModel,
    PCMChargeModel,
)
from gsy_e.models.strategy.energy_parameters.heatpump.pcm_tank_model.utils_constants import (
    MASS_FLOW_RATE,
    NUMBER_OF_PCM_ELEMENTS,
)
from gsy_e.models.strategy.energy_parameters.heatpump.tank_parameters import TankParameters
from gsy_e.models.strategy.state.base_states import TankStateBase
from gsy_e.models.strategy.state.heatpump_state import delete_time_slots_in_state


log = logging.getLogger()


class PCMTankState(TankStateBase):
    """State class for the PCM tank"""

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        tank_parameters: TankParameters,
    ):
        super().__init__(tank_parameters)
        self._htf_temps_C: Dict[DateTime, list[float]] = {}
        self._pcm_temps_C: Dict[DateTime, list[float]] = {}
        self._pcm_charge_model = PCMChargeModel(
            slot_length=GlobalConfig.slot_length, mass_flow_rate_kg_s=MASS_FLOW_RATE
        )
        self._pcm_discharge_model = PCMDischargeModel(
            slot_length=GlobalConfig.slot_length, mass_flow_rate_kg_s=MASS_FLOW_RATE
        )
        self._heat_demand_kJ: Dict[DateTime, float] = {}
        self._max_capacity_kJ = tank_parameters.max_capacity_kJ

    def serialize(self):
        """Return serializable dict of class parameters."""
        return {
            "initial_temp_C": self._params.initial_temp_C,
            "min_storage_temp_C": self._params.min_temp_C,
            "max_storage_temp_C": self._params.max_temp_C,
            "max_capacity_kJ": self._params.max_capacity_kJ,
        }

    def init(self):
        """
        Initiate the storage temperatures with the initial temperature of the storge
        """
        self._htf_temps_C[GlobalConfig.start_date] = [
            self._params.initial_temp_C for _ in range(int(NUMBER_OF_PCM_ELEMENTS / 2))
        ]
        self._pcm_temps_C[GlobalConfig.start_date] = [
            self._params.initial_temp_C for _ in range(int(NUMBER_OF_PCM_ELEMENTS / 2))
        ]
        self._soc[GlobalConfig.start_date] = (
            self._params.initial_temp_C - self._params.min_temp_C
        ) / (self._params.max_temp_C - self._params.min_temp_C)

    def _get_htf_temps_C(self, time_slot: DateTime) -> Optional[list]:
        return self._htf_temps_C.get(time_slot)

    def _get_pcm_temps_C(self, time_slot: DateTime) -> Optional[list]:
        return self._pcm_temps_C.get(time_slot)

    def _set_soc_after_charging(self, time_slot: DateTime):
        """Calculate and set SOC level after charging."""
        self._soc[time_slot] = self._pcm_charge_model.get_soc(self._get_pcm_temps_C(time_slot))

    def _set_soc_after_discharging(self, time_slot: DateTime):
        """Calculate and set SOC level after discharging."""
        self._soc[time_slot] = self._pcm_discharge_model.get_soc(self._get_pcm_temps_C(time_slot))

    def _get_heat_demand_kJ(self, time_slot: DateTime):
        return self._heat_demand_kJ.get(time_slot)

    def _set_heat_demand_kJ(self, energy_kJ: float, time_slot: DateTime):
        self._heat_demand_kJ[time_slot] = energy_kJ

    def get_htf_temp_C(self, time_slot: DateTime) -> Optional[float]:
        """Return mean temperature of the heat transfer fluid"""
        htf_temps = self._get_htf_temps_C(time_slot)
        return None if htf_temps is None else mean(htf_temps)

    def get_pcm_temp_C(self, time_slot: DateTime) -> Optional[float]:
        """Return the mean temperature of the PCM."""
        pcm_temps = self._get_pcm_temps_C(time_slot)
        return None if pcm_temps is None else mean(pcm_temps)

    def _get_deltaT_from_heat_demand_kWh(self, heat_energy_kWh: float) -> float:
        """
        Q > 0 --> dT >0
        Q < 0 --> dT <0
        """
        return convert_kWh_to_W(heat_energy_kWh, GlobalConfig.slot_length) / (
            MASS_FLOW_RATE * SPECIFIC_HEAT_CAPACITY_WATER
        )

    def _get_condenser_temp_from_heat_demand_kWh(
        self, heat_energy_kWh: float, time_slot: DateTime
    ):
        condenser_temp_C = self.get_htf_temp_C(time_slot) + self._get_deltaT_from_heat_demand_kWh(
            heat_energy_kWh
        )
        assert 0 < condenser_temp_C < 100, f"unrealistic condenser temp {condenser_temp_C}"
        return condenser_temp_C

    def _limit_condenser_temp(self, condenser_temp_C: float) -> float:
        if (self._params.min_temp_C - condenser_temp_C) > FLOATING_POINT_TOLERANCE:
            log.warning(
                "The PCM storage tank reached it's minimum (%s), discharging "
                "condensor temperature of %s is omitted",
                self._params.min_temp_C,
                round(condenser_temp_C, 2),
            )
            return self._params.min_temp_C
        if (condenser_temp_C - self._params.max_temp_C) > FLOATING_POINT_TOLERANCE:
            log.warning(
                "The PCM storage tank reached it's maximum (%s), charging "
                "condensor temperature of %s is omitted",
                self._params.max_temp_C,
                round(condenser_temp_C, 2),
            )
            return self._params.max_temp_C
        return condenser_temp_C

    def increase_tank_temp_from_heat_energy(self, heat_energy_kWh: float, time_slot: DateTime):
        """Increase the temperature of the water tank with the provided heat energy."""
        temp_cond_C = self._get_condenser_temp_from_heat_demand_kWh(
            heat_energy_kWh, self._last_time_slot(time_slot)
        )
        self._increase_storage_temp_from_condenser_temp(temp_cond_C, time_slot)

    def decrease_tank_temp_from_heat_energy(self, heat_energy_kWh: float, time_slot: DateTime):
        """Decrease the temperature of the water tank with the provided heat energy."""
        temp_cond_C = self._get_condenser_temp_from_heat_demand_kWh(
            -heat_energy_kWh, self._last_time_slot(time_slot)
        )
        self._decrease_storage_temp_from_condenser_temp(temp_cond_C, time_slot)

    def _increase_storage_temp_from_condenser_temp(
        self, condenser_temp_C: float, time_slot: DateTime
    ):
        """Increase storage temperatures for provided condenser temperature."""
        condenser_temp_C = self._limit_condenser_temp(condenser_temp_C)
        htf_temps, pcm_temps = self._pcm_charge_model.get_temp_after_charging(
            current_htf_temps_C=self._get_htf_temps_C(self._last_time_slot(time_slot)),
            current_pcm_temps_C=self._get_pcm_temps_C(self._last_time_slot(time_slot)),
            charging_temp=condenser_temp_C,
        )
        self._htf_temps_C[time_slot] = htf_temps
        self._pcm_temps_C[time_slot] = pcm_temps

        self._set_soc_after_charging(time_slot)

    def _decrease_storage_temp_from_condenser_temp(
        self, condenser_temp_C: float, time_slot: DateTime
    ):
        """Decrease storage temperatures for provided condenser temperature."""
        condenser_temp_C = self._limit_condenser_temp(condenser_temp_C)
        htf_temps, pcm_temps = self._pcm_discharge_model.get_temp_after_discharging(
            current_htf_temps_C=self._get_htf_temps_C(self._last_time_slot(time_slot)),
            current_pcm_temps_C=self._get_pcm_temps_C(self._last_time_slot(time_slot)),
            discharging_temp=condenser_temp_C,
        )
        self._htf_temps_C[time_slot] = htf_temps
        self._pcm_temps_C[time_slot] = pcm_temps

        self._set_soc_after_discharging(time_slot)

    def no_charge(self, time_slot: DateTime):
        self._htf_temps_C[time_slot] = self._get_htf_temps_C(self._last_time_slot(time_slot))
        self._pcm_temps_C[time_slot] = self._get_pcm_temps_C(self._last_time_slot(time_slot))
        self._soc[time_slot] = self._soc[self._last_time_slot(time_slot)]

    def get_results_dict(self, current_time_slot: Optional[DateTime] = None) -> dict:
        if current_time_slot is None:
            return {
                "soc": 0,
                "htf_temp_C": 0,
                "pcm_temp_C": 0,
                "storage_temp_C": 0,
                "type": "PCM",
                "name": self._params.name,
            }

        return {
            "soc": self.get_soc(current_time_slot),
            "htf_temp_C": self.get_htf_temp_C(current_time_slot),
            "pcm_temp_C": self.get_pcm_temp_C(current_time_slot),
            "storage_temp_C": self.get_pcm_temp_C(current_time_slot),
            "type": "PCM",
            "name": self._params.name,
        }

    def get_state(self) -> Dict:
        return {
            "htf_temps_C": convert_pendulum_to_str_in_dict(self._htf_temps_C),
            "pcm_temps_C": convert_pendulum_to_str_in_dict(self._pcm_temps_C),
            "soc": convert_pendulum_to_str_in_dict(self._soc),
            "min_storage_temp_C": self._params.min_temp_C,
            "max_storage_temp_C": self._params.max_temp_C,
            "max_capacity_kJ": self._params.max_capacity_kJ,
            "initial_temp_C": self._params.initial_temp_C,
        }

    def restore_state(self, state_dict: Dict):
        self._htf_temps_C = convert_str_to_pendulum_in_dict(state_dict["htf_temps_C"])
        self._pcm_temps_C = convert_str_to_pendulum_in_dict(state_dict["pcm_temps_C"])
        self._soc = convert_str_to_pendulum_in_dict(state_dict["soc"])
        self._params.min_temp_C = state_dict["min_storage_temp_C"]
        self._params.max_temp_C = state_dict["max_storage_temp_C"]
        self._params.max_capacity_kJ = state_dict["max_capacity_kJ"]
        self._params.initial_temp_C = state_dict["initial_temp_C"]

    def delete_past_state_values(self, current_time_slot: DateTime):
        if not current_time_slot or constants.RETAIN_PAST_MARKET_STRATEGIES_STATE:
            return
        last_time_slot = self._last_time_slot(current_time_slot)
        delete_time_slots_in_state(self._htf_temps_C, last_time_slot)
        delete_time_slots_in_state(self._pcm_temps_C, last_time_slot)
        delete_time_slots_in_state(self._soc, last_time_slot)

    def get_min_heat_energy_consumption_kJ(self, time_slot: DateTime, heat_demand_kJ: float):
        available_energy_kJ = self.get_available_energy_kJ(time_slot)
        if available_energy_kJ >= heat_demand_kJ:
            return 0
        return heat_demand_kJ - available_energy_kJ

    def get_max_heat_energy_consumption_kJ(self, time_slot: DateTime, heat_demand_kJ: float):
        return (
            self._params.max_capacity_kJ - self.get_available_energy_kJ(time_slot) + heat_demand_kJ
        )

    def current_tank_temperature(self, time_slot):
        return mean(self._pcm_temps_C[time_slot])
