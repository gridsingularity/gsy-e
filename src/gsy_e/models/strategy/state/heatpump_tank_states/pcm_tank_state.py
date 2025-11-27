import logging
from statistics import mean
from typing import Dict, Optional

from pendulum import DateTime

from gsy_framework.constants_limits import GlobalConfig, FLOATING_POINT_TOLERANCE
from gsy_framework.utils import (
    convert_pendulum_to_str_in_dict,
    convert_str_to_pendulum_in_dict,
    convert_kWh_to_W,
    convert_kWh_to_kJ,
    convert_W_to_kWh,
)

from gsy_e import constants

from gsy_e.models.strategy.energy_parameters.heatpump.constants import SPECIFIC_HEAT_CAPACITY_WATER
from gsy_e.models.strategy.energy_parameters.heatpump.pcm_tank_model.pcm_models import (
    PCMDischargeModel,
    PCMChargeModel,
)
from gsy_e.models.strategy.energy_parameters.heatpump.pcm_tank_model.utils_constants import (
    NUMBER_OF_PCM_ELEMENTS,
)
from gsy_e.models.strategy.energy_parameters.heatpump.tank_parameters import PCMTankParameters
from gsy_e.models.strategy.state.base_states import TankStateBase
from gsy_e.models.strategy.state.heatpump_state import delete_time_slots_in_state

log = logging.getLogger()


class PCMTankState(TankStateBase):
    """State class for the PCM tank"""

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        tank_parameters: PCMTankParameters,
    ):
        super().__init__(tank_parameters)
        self._htf_temps_C: Dict[DateTime, list[float]] = {}
        self._pcm_temps_C: Dict[DateTime, list[float]] = {}
        self._condenser_temp_C: Dict[DateTime, float] = {}
        self._pcm_charge_model = PCMChargeModel(
            slot_length=GlobalConfig.slot_length,
            mass_flow_rate_kg_s=self._mass_flow_rate_per_plate,
            pcm_type=tank_parameters.pcm_tank_type,
        )
        self._pcm_discharge_model = PCMDischargeModel(
            slot_length=GlobalConfig.slot_length,
            mass_flow_rate_kg_s=self._mass_flow_rate_per_plate,
            pcm_type=tank_parameters.pcm_tank_type,
        )
        self._heat_demand_kJ: Dict[DateTime, float] = {}

    def serialize(self):
        """Return serializable dict of class parameters."""
        return {
            "initial_temp_C": self._params.initial_temp_C,
            "min_temp_htf_C": self._params.min_temp_htf_C,
            "max_temp_htf_C": self._params.max_temp_htf_C,
            "min_temp_pcm_C": self._params.min_temp_pcm_C,
            "max_temp_pcm_C": self._params.max_temp_pcm_C,
            "type": self._params.type.value,
            "pcm_tank_type": self._params.pcm_tank_type.value,
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
        self._condenser_temp_C[GlobalConfig.start_date] = self._params.initial_temp_C
        self._soc[GlobalConfig.start_date] = self._pcm_charge_model.get_soc(
            self._get_pcm_temps_C(GlobalConfig.start_date)
        )

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

    def _set_condenser_temp_C(self, temp_C: float, time_slot: DateTime):
        self._condenser_temp_C[time_slot] = temp_C

    def _get_condenser_temp_C(self, time_slot: DateTime):
        return self._condenser_temp_C.get(time_slot, self.get_htf_temp_C(time_slot))

    def get_htf_temp_C(self, time_slot: DateTime) -> Optional[float]:
        """Return mean temperature of the heat transfer fluid"""
        htf_temps = self._get_htf_temps_C(time_slot)
        return None if htf_temps is None else mean(htf_temps)

    def get_pcm_temp_C(self, time_slot: DateTime) -> Optional[float]:
        """Return the mean temperature of the PCM."""
        pcm_temps = self._get_pcm_temps_C(time_slot)
        return None if pcm_temps is None else mean(pcm_temps)

    def _get_deltaT_from_heat_demand_kWh(self, heat_energy_kWh: float) -> float:
        """dT[K] = Q / (m + c_p)"""
        return convert_kWh_to_W(heat_energy_kWh, GlobalConfig.slot_length) / (
            self._mass_flow_rate_on_inlet * SPECIFIC_HEAT_CAPACITY_WATER
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
        if (self._params.min_temp_htf_C - condenser_temp_C) > FLOATING_POINT_TOLERANCE:
            log.warning(
                "The PCM storage tank reached it's minimum (%s), discharging "
                "condensor temperature of %s is limited to the minimum",
                self._params.min_temp_htf_C,
                round(condenser_temp_C, 2),
            )
        if (condenser_temp_C - self._params.max_temp_htf_C) > FLOATING_POINT_TOLERANCE:
            log.warning(
                "The PCM storage tank reached it's maximum (%s), charging "
                "condensor temperature of %s is limited to the maximum",
                self._params.max_temp_htf_C,
                round(condenser_temp_C, 2),
            )
        return condenser_temp_C

    def increase_tank_temp_from_heat_energy(self, heat_energy_kWh: float, time_slot: DateTime):
        """Increase the temperature of the water tank with the provided heat energy."""
        assert heat_energy_kWh > FLOATING_POINT_TOLERANCE
        temp_cond_C = self._get_condenser_temp_from_heat_demand_kWh(
            heat_energy_kWh, self._last_time_slot(time_slot)
        )
        self._increase_storage_temp_from_condenser_temp(temp_cond_C, time_slot)

    def decrease_tank_temp_from_heat_energy(self, heat_energy_kWh: float, time_slot: DateTime):
        """Decrease the temperature of the water tank with the provided heat energy."""
        assert heat_energy_kWh > FLOATING_POINT_TOLERANCE
        temp_cond_C = self._get_condenser_temp_from_heat_demand_kWh(
            -heat_energy_kWh, self._last_time_slot(time_slot)
        )
        self._decrease_storage_temp_from_condenser_temp(temp_cond_C, time_slot)

    def _increase_storage_temp_from_condenser_temp(
        self, condenser_temp_C: float, time_slot: DateTime
    ):
        """Increase storage temperatures for provided condenser temperature."""
        condenser_temp_C = self._limit_condenser_temp(condenser_temp_C)
        self._set_condenser_temp_C(condenser_temp_C, time_slot)
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
        self._set_condenser_temp_C(condenser_temp_C, time_slot)
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
        self._pcm_temps_C[time_slot] = self._get_htf_temps_C(self._last_time_slot(time_slot))
        self._set_soc_after_charging(time_slot)
        self._set_condenser_temp_C(self.get_htf_temp_C(time_slot), time_slot)

    def get_results_dict(self, current_time_slot: Optional[DateTime] = None) -> dict:
        if current_time_slot is None:
            return {
                "soc": 0,
                "htf_temp_C": 0,
                "pcm_temp_C": 0,
                "storage_temp_C": 0,
                "type": "PCM",
                "name": self._params.name,
                "condenser_temp_C": 0,
            }

        return {
            "soc": self.get_soc(current_time_slot),
            "htf_temp_C": self.get_htf_temp_C(current_time_slot),
            "pcm_temp_C": self.get_pcm_temp_C(current_time_slot),
            "storage_temp_C": self.get_pcm_temp_C(current_time_slot),
            "type": "PCM",
            "name": self._params.name,
            "condenser_temp_C": self._get_condenser_temp_C(current_time_slot),
        }

    def get_state(self) -> Dict:
        return {
            "htf_temps_C": convert_pendulum_to_str_in_dict(self._htf_temps_C),
            "pcm_temps_C": convert_pendulum_to_str_in_dict(self._pcm_temps_C),
            "condenser_temp_C": convert_pendulum_to_str_in_dict(self._condenser_temp_C),
            "soc": convert_pendulum_to_str_in_dict(self._soc),
        }

    def restore_state(self, state_dict: Dict):
        self._htf_temps_C = convert_str_to_pendulum_in_dict(state_dict["htf_temps_C"])
        self._pcm_temps_C = convert_str_to_pendulum_in_dict(state_dict["pcm_temps_C"])
        self._condenser_temp_C = convert_str_to_pendulum_in_dict(state_dict["condenser_temp_C"])
        self._soc = convert_str_to_pendulum_in_dict(state_dict["soc"])
        self._params.min_temp_htf_C = state_dict["min_temp_htf_C"]
        self._params.max_temp_htf_C = state_dict["max_temp_htf_C"]
        self._params.min_temp_pcm_C = state_dict["min_temp_pcm_C"]
        self._params.max_temp_pcm_C = state_dict["max_temp_pcm_C"]
        self._params.initial_temp_C = state_dict["initial_temp_C"]

    def delete_past_state_values(self, current_time_slot: DateTime):
        if not current_time_slot or constants.RETAIN_PAST_MARKET_STRATEGIES_STATE:
            return
        last_time_slot = self._last_time_slot(current_time_slot)
        delete_time_slots_in_state(self._htf_temps_C, last_time_slot)
        delete_time_slots_in_state(self._pcm_temps_C, last_time_slot)
        delete_time_slots_in_state(self._soc, last_time_slot)

    def get_min_heat_energy_consumption_kJ(self, time_slot: DateTime, heat_demand_kJ: float):
        available_energy_kJ = self.get_soc_energy_kJ(time_slot)
        if available_energy_kJ >= heat_demand_kJ:
            return 0
        return heat_demand_kJ - available_energy_kJ

    def get_soc_energy_kJ(self, time_slot: DateTime) -> float:
        """Return the available energy stored in the tank."""
        if self.get_pcm_temp_C(time_slot) - self._params.min_temp_pcm_C < FLOATING_POINT_TOLERANCE:
            return 0

        return convert_kWh_to_kJ(
            self._get_heat_demand_kWh_from_deltaT(
                self.get_pcm_temp_C(time_slot) - self._params.min_temp_pcm_C
            )
        )

    def get_max_heat_energy_consumption_kJ(
        self, time_slot: DateTime, heat_demand_kJ: float
    ) -> float:
        return self.get_dod_energy_kJ(time_slot) + heat_demand_kJ

    def _get_heat_demand_kWh_from_deltaT(self, temperature_difference: float) -> float:
        """Q[W]= m[kg/s] * c_p[W * s/ (kg * K)] * dT[K]"""
        return convert_W_to_kWh(
            self._mass_flow_rate_on_inlet * SPECIFIC_HEAT_CAPACITY_WATER * temperature_difference,
            GlobalConfig.slot_length,
        )

    def get_dod_energy_kJ(self, time_slot: DateTime) -> float:
        """Return depth of discharge as an energy value in kJ."""
        if self._params.max_temp_pcm_C - self.get_pcm_temp_C(time_slot) < FLOATING_POINT_TOLERANCE:
            return 0

        return convert_kWh_to_kJ(
            self._get_heat_demand_kWh_from_deltaT(
                self._params.max_temp_pcm_C - self.get_pcm_temp_C(time_slot)
            )
        )

    def current_tank_temperature(self, time_slot):
        return mean(self._pcm_temps_C[time_slot])

    def current_condenser_temperature(self, time_slot):
        return self._get_condenser_temp_C(time_slot)

    @property
    def _mass_flow_rate_on_inlet(self) -> float:
        return self._params.volume_flow_rate_l_min / 60

    @property
    def _mass_flow_rate_per_plate(self) -> float:
        return self._mass_flow_rate_on_inlet / self._params.number_of_plates

    def _apply_losses(self, time_slot: DateTime):
        per_market_slot_loss_htf_C = (
            self.get_htf_temp_C(time_slot) * self._params.per_market_slot_loss
        )
        self._htf_temps_C[time_slot] = [
            v - per_market_slot_loss_htf_C for v in self._htf_temps_C[time_slot]
        ]
        per_market_slot_loss_pcm_C = (
            self.get_pcm_temp_C(time_slot) * self._params.per_market_slot_loss
        )
        self._pcm_temps_C[time_slot] = [
            v - per_market_slot_loss_pcm_C for v in self._pcm_temps_C[time_slot]
        ]
