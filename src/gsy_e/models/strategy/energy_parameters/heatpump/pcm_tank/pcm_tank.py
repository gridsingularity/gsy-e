from typing import Dict
from collections import defaultdict
from statistics import mean
from pendulum import DateTime, duration
from dataclasses import dataclass
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.utils import convert_kWh_to_W

from gsy_e.models.strategy.energy_parameters.heatpump.tank import (
    TankEnergyParameters,
    TankParameters,
)
from gsy_e.models.strategy.energy_parameters.heatpump.constants import SPECIFIC_HEAT_CAPACITY_WATER
from gsy_e.models.strategy.energy_parameters.heatpump.pcm_tank.pcm_models import (
    PCMDischargeModel,
    PCMChargeModel,
)
from gsy_e.models.strategy.state.base_states import StateInterface


@dataclass
class PCMTankParameters:
    """Nameplate parameters of a water tank."""

    min_temp_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C
    max_temp_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C
    initial_temp_C: float = ConstSettings.HeatPumpSettings.INIT_TEMP_C
    max_capacity_kWh: float = 0.0


MASS_FLOW_RATE = 1.8440 / 60  # kg/s
SCALING_FACTOR_COP_CARNOT = 0.5
NUMBER_OF_PCM_ELEMENTS = 10


class PCMTankState(StateInterface):

    def __init__(
        self,
        initial_temp_C: float,
        slot_length: duration,
        min_storage_temp_C: float,
        max_storage_temp_C: float,
    ):
        self.storage_temp_C: list[float] = [initial_temp_C for _ in range(NUMBER_OF_PCM_ELEMENTS)]
        self._temp_decrease_K: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._temp_increase_K: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._min_storage_temp_C = min_storage_temp_C
        self._max_storage_temp_C = max_storage_temp_C
        self._slot_length = slot_length
        self._soc = Dict[DateTime, float] = defaultdict(lambda: 0)

    def set_soc(self, soc: float, time_slot: DateTime) -> float:
        """Set SOC"""
        # TODO

    def get_soc(self, time_slot: DateTime) -> float:
        "Return SOC."
        # TODO

    def get_state(self) -> Dict:
        # TODO
        return {}

    def get_htf_temps(self):
        return mean(self.storage_temp_C[0:-2:2])

    def get_pcm_temps(self):
        return mean(self.storage_temp_C[1:-1:2])


class PCMTankEnergyParameters:

    def __init__(self, tank_parameters: PCMTankParameters, slot_length):

        self._state = PCMTankState(
            initial_temp_C=tank_parameters.initial_temp_C,
            slot_length=slot_length,
            min_storage_temp_C=tank_parameters.min_temp_C,
            max_storage_temp_C=tank_parameters.max_temp_C,
        )
        self._pcm_charge_model = PCMChargeModel()
        self._pcm_discharge_model = PCMDischargeModel()
        self._max_capacity_kWh = tank_parameters.max_capacity_kWh

    def serialize(self):
        return {}

    def _get_condensor_temp_from_cop(self, time_slot: DateTime):
        """
        Basis of this is the relation: COP = SCALING_FACTOR_COP_CARNOT * eta
        where eta is the carnot efficiency:
        eta = T_cond / (T_cond - T_source)
        """
        # todo: outdated, we should not use this relation
        cop = self._state.get_cop(time_slot)
        return cop * self._state.get_storage_temp_C(time_slot) / (cop - SCALING_FACTOR_COP_CARNOT)

    def _get_condensor_temp_from_heat_demand(
        self, heat_energy_kWh: float, source_temperature: float
    ) -> float:
        """
        Basis of this calculation is the Q = m * c * dT relation, where
        Q = heat demand power [W]
        m = mass flow rate [kg/s]
        c = specific heat capacity (of water) [J / kg / K]
        dT = temperature difference to the inserted heat (T_i+1 - T_i)
        """
        return (
            convert_kWh_to_W(heat_energy_kWh, GlobalConfig.slot_length)
            / (MASS_FLOW_RATE * SPECIFIC_HEAT_CAPACITY_WATER)
            + source_temperature
        )

    def increase_tank_temp_from_heat_energy(self, heat_energy_kWh: float, time_slot: DateTime):
        # todo: implement: get_source_temp or pass it from caller code
        temp_cond_C = self._get_condensor_temp_from_heat_demand(
            heat_energy_kWh, source_temperature
        )
        self._increase_storage_temp_from_condensor_temp(temp_cond_C)

    def decrease_tank_temp_from_heat_energy(self, heat_energy_kWh: float, time_slot: DateTime):
        # todo: implement: get_source_temp or pass it from caller code
        temp_cond_C = self._get_condensor_temp_from_heat_demand(
            heat_energy_kWh, source_temperature
        )
        self._decrease_storage_temp_from_condensor_temp(temp_cond_C)

    def set_soc(self, time_slot: DateTime):
        self._state.set_soc(self._pcm_charge_model.get_soc(self._state.storage_temp_C), time_slot)

    def _increase_storage_temp_from_condensor_temp(self, charging_temp_C: float):
        temperatures_after_charging = self._pcm_charge_model.get_temp_after_charging(
            current_storage_temps=self._state.storage_temp_C,
            mass_flow_kg_s=MASS_FLOW_RATE,
            charging_temp=charging_temp_C,
        )
        self._state.storage_temp_C = temperatures_after_charging

    def _decrease_storage_temp_from_condensor_temp(self, discharging_temp_C: float):
        temperatures_after_discharging = self._pcm_discharge_model.get_temp_after_discharging(
            current_storage_temps=self._state.storage_temp_C,
            mass_flow_kg_s=MASS_FLOW_RATE,
            discharging_temp=discharging_temp_C,
        )
        self._state.storage_temp_C = temperatures_after_discharging

    def get_max_energy_consumption(self, time_slot: DateTime):
        """Calculate max energy consumption that a heatpump with provided COP can consume."""
        return self._max_capacity_kWh - self._state.get_soc(time_slot) * self._max_capacity_kWh

    def get_min_energy_consumption(self, energy_demand_kWh: float):
        """the minimum"""
        # todo: the minimum should be the demand, bordered by the available SOC, something like:
        available_soc_kWh = self.get_max_energy_consumption()
        if available_soc_kWh > energy_demand_kWh:
            return energy_demand_kWh
        return available_soc_kWh


class PCMHeatPumpState:

    def __init__(self, slot_length: duration, max_capacity_kWh):
        # the defaultdict was only selected for the initial slot
        self._min_energy_demand_kWh: Dict[DateTime, float] = {}
        self._max_energy_demand_kWh: Dict[DateTime, float] = {}
        # buffers for increase and  decrease of storage
        self._energy_consumption_kWh: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._unmatched_demand_kWh: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._cop: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._condenser_temp_C: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._heat_demand_J: Dict[DateTime, float] = defaultdict(lambda: 0)
        self._total_traded_energy_kWh: float = 0
        self._slot_length = slot_length
        self._max_capacity_kWh = max_capacity_kWh

    def get_min_energy_consumption(self, cop: float, time_slot: DateTime):
        """"""
        # return self._state.get_temp_decrease_K(time_slot) * self._Q_specific / cop

        self.get_available_energy_from_SOC
        # here we need to somehow calculate the minimum energy consumption
        # questions:
        # How can we find out how much energy is needed to fulfill the basic demand? only bc P/COP?
        # Is the cop->T_cond->storage approach really physically plausible?
