import logging
from typing import Optional, Union, Dict, List

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.read_user_profile import InputProfileTypes
from pendulum import DateTime

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.energy_parameters.heatpump.heat_pump import HeatPumpEnergyParametersBase
from gsy_e.models.strategy.energy_parameters.heatpump.tank import (
    VirtualHeatpumpAllTanksEnergyParameters,
    TankParameters,
)
from gsy_e.models.strategy.energy_parameters.heatpump.constants import (
    WATER_SPECIFIC_HEAT_CAPACITY,
    DEFAULT_SOURCE_TEMPERATURE_C,
)
from gsy_e.models.strategy.energy_parameters.heatpump.virtual_heatpump_solver import (
    VirtualHeatpumpSolverParameters,
    VirtualHeatpumpStorageEnergySolver,
)
from gsy_e.models.strategy.strategy_profile import StrategyProfile

logger = logging.getLogger(__name__)


class VirtualHeatpumpEnergyParameters(HeatPumpEnergyParametersBase):
    """Energy parameters for the virtual heatpump strategy class."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        maximum_power_rating_kW: float = ConstSettings.HeatPumpSettings.MAX_POWER_RATING_KW,
        tank_parameters: List[TankParameters] = None,
        water_supply_temp_C_profile: Optional[Union[str, float, Dict]] = None,
        water_supply_temp_C_profile_uuid: Optional[str] = None,
        water_return_temp_C_profile: Optional[Union[str, float, Dict]] = None,
        water_return_temp_C_profile_uuid: Optional[str] = None,
        source_temp_C_profile: Optional[Union[str, float, Dict]] = DEFAULT_SOURCE_TEMPERATURE_C,
        source_temp_C_profile_uuid: Optional[str] = None,
        dh_water_flow_m3_profile: Optional[Union[str, float, Dict]] = None,
        dh_water_flow_m3_profile_uuid: Optional[str] = None,
        calibration_coefficient: Optional[float] = None,
    ):
        super().__init__(
            maximum_power_rating_kW=maximum_power_rating_kW, tank_parameters=tank_parameters
        )
        if not tank_parameters:
            tank_parameters = [TankParameters()]

        self._tanks = VirtualHeatpumpAllTanksEnergyParameters(tank_parameters)

        self._water_supply_temp_C: [DateTime, float] = StrategyProfile(
            water_supply_temp_C_profile,
            water_supply_temp_C_profile_uuid,
            profile_type=InputProfileTypes.IDENTITY,
        )

        self._water_return_temp_C: [DateTime, float] = StrategyProfile(
            water_return_temp_C_profile,
            water_return_temp_C_profile_uuid,
            profile_type=InputProfileTypes.IDENTITY,
        )

        self._dh_water_flow_m3: [DateTime, float] = StrategyProfile(
            dh_water_flow_m3_profile,
            dh_water_flow_m3_profile_uuid,
            profile_type=InputProfileTypes.IDENTITY,
        )

        self._source_temp_C_profile: [DateTime, float] = StrategyProfile(
            source_temp_C_profile,
            source_temp_C_profile_uuid,
            profile_type=InputProfileTypes.IDENTITY,
        )
        print("self.source_temp_C_profile.profile", self._source_temp_C_profile.profile)

        self.calibration_coefficient = (
            calibration_coefficient
            if calibration_coefficient is not None
            else ConstSettings.HeatPumpSettings.CALIBRATION_COEFFICIENT
        )

    def serialize(self):
        """Return dict with the current energy parameter values."""
        return {
            **self._tanks.serialize(),
            "max_energy_consumption_kWh": self._max_energy_consumption_kWh,
            "maximum_power_rating_kW": self._maximum_power_rating_kW,
            "water_supply_temp_C": self._water_supply_temp_C.input_profile,
            "water_supply_temp_C_uuid": self._water_supply_temp_C.input_profile_uuid,
            "water_return_temp_C": self._water_return_temp_C.input_profile,
            "water_return_temp_C_uuid": self._water_return_temp_C.input_profile_uuid,
            "dh_water_flow_m3_profile": self._dh_water_flow_m3.input_profile,
            "dh_water_flow_m3_profile_uuid": self._dh_water_flow_m3.input_profile_uuid,
        }

    def _rotate_profiles(self, current_time_slot: Optional[DateTime] = None):
        self._water_return_temp_C.read_or_rotate_profiles()
        self._water_supply_temp_C.read_or_rotate_profiles()
        self._dh_water_flow_m3.read_or_rotate_profiles()
        self._source_temp_C_profile.read_or_rotate_profiles()
        self._state.heatpump.delete_past_state_values(current_time_slot)

    def _calc_energy_to_buy_maximum(self, time_slot: DateTime) -> float:
        max_energy_consumption = self._max_tank_temp_to_energy(time_slot)
        assert max_energy_consumption > -FLOATING_POINT_TOLERANCE
        return min(self._max_energy_consumption_kWh, max_energy_consumption)

    def _calc_energy_to_buy_minimum(self, time_slot: DateTime) -> float:
        min_energy_consumption = self._current_tank_temp_to_energy(time_slot)
        assert min_energy_consumption > -FLOATING_POINT_TOLERANCE
        return min(self._max_energy_consumption_kWh, min_energy_consumption)

    def _set_temp_decrease_for_all_tanks(self, time_slot: DateTime):
        dh_supply_temp = self._water_supply_temp_C.get_value(time_slot)
        dh_return_temp = self._water_return_temp_C.get_value(time_slot)
        m_m3 = self._dh_water_flow_m3.get_value(time_slot)
        m_kg_per_sec = m_m3 * 1000 / 3600
        q_out = m_kg_per_sec * WATER_SPECIFIC_HEAT_CAPACITY * (dh_supply_temp - dh_return_temp)

        tank_solver_parameters = self._tanks.set_temp_decrease_vhp(q_out, time_slot)
        if tank_solver_parameters:
            heatpump_parameters = VirtualHeatpumpSolverParameters(
                dh_supply_temp_C=self._water_supply_temp_C.get_value(time_slot),
                dh_return_temp_C=self._water_return_temp_C.get_value(time_slot),
                dh_flow_m3_per_hour=self._dh_water_flow_m3.get_value(time_slot),
                source_temp_C=self._source_temp_C_profile.get_value(time_slot),
                calibration_coefficient=self.calibration_coefficient,
            )
            solver = VirtualHeatpumpStorageEnergySolver(
                tank_parameters=tank_solver_parameters, heatpump_parameters=heatpump_parameters
            )
            solver.calculate_energy_from_storage_temp()
            logger.debug(solver)
            self._state.heatpump.set_unmatched_demand_kWh(time_slot, solver.energy_kWh)

    def _current_tank_temp_to_energy(self, time_slot: DateTime) -> float:
        """
        Return the energy needed to be consumed by the heatpump in order to generate enough heat
        to maintain the same tank temp in degrees C.
        """
        tank_parameters = self._tanks.create_tank_solver_for_maintaining_tank_temperature(
            time_slot
        )

        heatpump_parameters = VirtualHeatpumpSolverParameters(
            dh_supply_temp_C=self._water_supply_temp_C.get_value(time_slot),
            dh_return_temp_C=self._water_return_temp_C.get_value(time_slot),
            dh_flow_m3_per_hour=self._dh_water_flow_m3.get_value(time_slot),
            source_temp_C=self._source_temp_C_profile.get_value(time_slot),
            calibration_coefficient=self.calibration_coefficient,
        )

        solver = VirtualHeatpumpStorageEnergySolver(
            tank_parameters=tank_parameters, heatpump_parameters=heatpump_parameters
        )
        solver.calculate_energy_from_storage_temp()

        logger.debug(solver)
        return solver.energy_kWh

    def _max_tank_temp_to_energy(self, time_slot: DateTime) -> float:
        """
        Return the energy needed to be consumed by the heatpump in order to generate enough heat
        to warm the water tank to its maximum temperature.
        """
        tank_parameters = self._tanks.create_tank_parameters_for_maxing_tank_temperature(time_slot)

        heatpump_parameters = VirtualHeatpumpSolverParameters(
            dh_supply_temp_C=self._water_supply_temp_C.get_value(time_slot),
            dh_return_temp_C=self._water_return_temp_C.get_value(time_slot),
            dh_flow_m3_per_hour=self._dh_water_flow_m3.get_value(time_slot),
            source_temp_C=self._source_temp_C_profile.get_value(time_slot),
            calibration_coefficient=self.calibration_coefficient,
        )

        solver = VirtualHeatpumpStorageEnergySolver(
            tank_parameters=tank_parameters, heatpump_parameters=heatpump_parameters
        )
        solver.calculate_energy_from_storage_temp()

        logger.debug(solver)
        return solver.energy_kWh

    def increase_tanks_temp_update_hp_state(self, energy_kWh: float, time_slot: DateTime):
        """
        Update the water tanks temperature after the heatpump has consumed energy_kWh energy and
        produced heat with it.
        """
        # pylint: disable=too-many-locals

        heatpump_parameters = VirtualHeatpumpSolverParameters(
            dh_supply_temp_C=self._water_supply_temp_C.get_value(time_slot),
            dh_return_temp_C=self._water_return_temp_C.get_value(time_slot),
            dh_flow_m3_per_hour=self._dh_water_flow_m3.get_value(time_slot),
            source_temp_C=self._source_temp_C_profile.get_value(time_slot),
            calibration_coefficient=self.calibration_coefficient,
            energy_kWh=energy_kWh,
        )

        solver = self._tanks.increase_tanks_temperature_with_energy_vhp(
            heatpump_parameters, time_slot
        )

        # Update last slot statistics (COP, heat demand, condenser temp)
        self._state.heatpump.set_cop(time_slot, solver.cop)
        self._state.heatpump.set_condenser_temp(time_slot, solver.condenser_temp_C)
        self._state.heatpump.set_heat_demand(time_slot, solver.q_out_J)

    def event_traded_energy(self, time_slot: DateTime, energy_kWh: float):
        """React to an event_traded_energy."""
        self._decrement_posted_energy(time_slot, energy_kWh)
        self._state.heatpump.update_energy_consumption_kWh(time_slot, energy_kWh)

    def _populate_state(self, time_slot: DateTime):
        last_time_slot = self.last_time_slot(time_slot)
        if last_time_slot in self._water_supply_temp_C.profile:
            # Update temp increase
            energy_kWh = self._state.heatpump.get_energy_consumption_kWh(last_time_slot)
            self.increase_tanks_temp_update_hp_state(energy_kWh, last_time_slot)

        self._tanks.update_tanks_temperature(time_slot)

        self._set_temp_decrease_for_all_tanks(time_slot)

        self._calc_energy_demand(time_slot)

    def event_market_cycle(self, current_time_slot):
        """To be called at the start of the market slot."""
        self._rotate_profiles(current_time_slot)
        self._populate_state(current_time_slot)
        supply_temp = self._water_supply_temp_C.get_value(current_time_slot)
        return_temp = self._water_return_temp_C.get_value(current_time_slot)
        assert supply_temp >= return_temp, (
            f"Supply temperature {supply_temp} has to be greater "
            f"than {return_temp}, timeslot {current_time_slot}"
        )
