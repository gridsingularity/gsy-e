from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Union
from logging import getLogger
from math import isclose

import numpy as np
from gsy_framework.constants_limits import GlobalConfig, ConstSettings, FLOATING_POINT_TOLERANCE
from gsy_framework.enums import AvailableMarketTypes, HeatPumpSourceType
from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.utils import (
    convert_kJ_to_kWh,
    convert_pendulum_to_str_in_dict,
    convert_str_to_pendulum_in_dict,
    convert_kW_to_kWh,
)
from pendulum import DateTime

from gsy_e.constants import SorTesConfiguration, RETAIN_PAST_MARKET_STRATEGIES_STATE, DEFAULT_COP
from gsy_e.models.strategy.energy_parameters.heatpump.cop_models import (
    COPModelType,
    cop_model_factory,
)
from gsy_e.models.strategy.heat_pump import HeatPumpOrderUpdaterParameters, HeatPumpStrategyBase
from gsy_e.models.strategy.heat_pump_soc_management import (
    MinimiseHeatpumpSwitchStrategy,
    HeatPumpChargingState,
)
from gsy_e.models.strategy.state.heatpump_state import (
    HeatPumpStateBase,
)
from gsy_e.models.strategy.strategy_profile import profile_factory, StrategyProfileBase

if TYPE_CHECKING:
    from gsy_e.models.market import MarketBase

log = getLogger(__name__)


class SorTesPerformanceMaps:
    """Calculate the charging and discharging performance of the SorTES tank"""

    CHARGING_POWER_MAP = {
        5: 3.8,
        10: 3.5,
        15: 3.3,
        20: 3.0,
        25: 2.6,
        30: 2.2,
        35: 1.8,
        40: 1.5,
        45: 0.5,
    }  # ambient_temp [K]: power [kW]
    DISCHARGING_POWER_MAP = {
        5: 3.0,
        10: 3.5,
        15: 4,
        20: 4.3,
        25: 4.8,
    }  # ambient_temp [K]: power [kW]

    @classmethod
    def get_power_charging(cls, temperature: float) -> float:
        """Return the charging power."""
        return cls._get_power(temperature, cls.CHARGING_POWER_MAP)

    @classmethod
    def get_power_discharging(cls, temperature: float) -> float:
        """Return the discharging power."""
        return cls._get_power(temperature, cls.DISCHARGING_POWER_MAP)

    @classmethod
    def _get_power(cls, temperature: float, power_table: dict) -> float:
        temps = np.array(sorted(power_table.keys()), dtype=float)
        powers = np.array([power_table[t] for t in sorted(power_table.keys())], dtype=float)

        return float(
            np.interp(temperature, temps, powers, left=None, right=None)
            if temps[0] <= temperature <= temps[-1]
            else cls._extrapolate(temperature, temps, powers)
        )

    @staticmethod
    def _extrapolate(temperature: float, temps: np.ndarray, powers: np.ndarray) -> float:
        """Linear extrapolation using the two nearest edge points."""
        if temperature < temps[0]:
            # Use the first two points for left extrapolation
            slope = (powers[1] - powers[0]) / (temps[1] - temps[0])
            return powers[0] + slope * (temperature - temps[0])
        # Use the last two points for right extrapolation
        slope = (powers[-1] - powers[-2]) / (temps[-1] - temps[-2])
        return powers[-1] + slope * (temperature - temps[-1])


class SorTesTankMinimiseSwitchStrategy(MinimiseHeatpumpSwitchStrategy):
    """Minimise number of switches between charging and discharging of the SorTES tank"""

    MINUTES_BEFORE_SWITCH_ALLOWED = SorTesConfiguration.MINUTES_BEFORE_SWITCH_ALLOWED
    MIN_SOC_TOLERANCE = SorTesConfiguration.MIN_SOC_TOLERANCE
    MAX_SOC_TOLERANCE = SorTesConfiguration.MAX_SOC_TOLERANCE

    # pylint: disable=super-init-not-called
    def __init__(
        self,
        energy_params: "SorTesTankEnergyParameters",
        average_trade_rate: Union[str, float, dict],
    ):
        self._last_switch: Optional[DateTime] = None
        self._energy_params = energy_params
        self._current_state = HeatPumpChargingState.MAINTAIN_SOC
        self._average_trade_rate = profile_factory(
            average_trade_rate, None, profile_type=InputProfileTypes.IDENTITY
        )

    @property
    def current_state(self) -> HeatPumpChargingState:
        """Return the current charging state of the tank."""
        return self._current_state

    def _get_tank_soc(self, time_slot: DateTime):
        return self._energy_params.get_soc(time_slot)

    def _is_energy_affordable(self, time_slot: DateTime, _buy_rate: float) -> bool:
        rates_in_time_horizont = [
            value
            for ts, value in self._average_trade_rate.profile.items()
            if time_slot
            <= ts
            < time_slot.add(minutes=SorTesConfiguration.MINUTES_TIME_HORIZONT_LOW_RATES)
        ]
        return all(
            value < SorTesConfiguration.PREFERRED_BUYING_RATE for value in rates_in_time_horizont
        )

    def event_activate(self):
        """Perform commands on event activate."""
        self._average_trade_rate.read_or_rotate_profiles()

    def event_market_slot(self):
        """Perform commands on event market cycle."""
        self._average_trade_rate.read_or_rotate_profiles()


class SorTesTankState(HeatPumpStateBase):
    """State class of Sortes tank state."""

    # pylint: disable=too-many-instance-attributes, super-init-not-called

    def __init__(self):
        self._soc: dict[DateTime, float] = {}
        self._cop: dict[DateTime, float] = {}  # in percent
        self._energy_demand_kWh: dict[DateTime, float] = {}  # electricity
        self._heat_demand_kJ: dict[DateTime, float] = {}
        self._min_energy_demand_kWh: dict[DateTime, float] = {}
        self._max_energy_demand_kWh: dict[DateTime, float] = {}
        self._total_traded_energy_kWh: float = 0  # for KPI calculation
        self._total_charged_energy_kWh: float = 0

    def update_total_charged_energy_kWh(self, charged_energy_kWh: float):
        """Update the total charged energy."""
        self._total_charged_energy_kWh += charged_energy_kWh

    def activate(self):
        """Perform commands on event activate."""
        self._soc[GlobalConfig.start_date] = SorTesConfiguration.MIN_SOC_TOLERANCE
        self._cop[GlobalConfig.start_date] = DEFAULT_COP

    def get_soc(self, time_slot: DateTime) -> float:
        """Return the soc value for the given time slot."""
        return self._soc.get(time_slot, 0)

    def set_soc(self, time_slot: DateTime, soc: float):
        """Set soc value for the given time slot."""
        self._soc[time_slot] = soc

    def get_min_energy_demand_kWh(self, time_slot: DateTime) -> float:
        """Return the minimal energy demanded for a given time slot."""
        return self._min_energy_demand_kWh.get(time_slot, 0)

    def get_max_energy_demand_kWh(self, time_slot: DateTime) -> float:
        """Return the maximal energy demanded for a given time slot."""
        return self._max_energy_demand_kWh.get(time_slot, 0)

    def set_min_energy_demand_kWh(self, time_slot: DateTime, energy_kWh: float):
        """Set the minimal energy demanded for a given time slot."""
        self._min_energy_demand_kWh[time_slot] = energy_kWh

    def set_max_energy_demand_kWh(self, time_slot: DateTime, energy_kWh: float):
        """Set the maximal energy demanded for a given time slot."""
        self._max_energy_demand_kWh[time_slot] = energy_kWh

    def delete_past_state_values(self, current_time_slot: Optional[DateTime] = None):
        """Delete past state values."""
        if not current_time_slot or RETAIN_PAST_MARKET_STRATEGIES_STATE:
            return
        last_time_slot = self._last_time_slot(current_time_slot)
        self._delete_time_slots(self._cop, last_time_slot)
        self._delete_time_slots(self._soc, last_time_slot)
        self._delete_time_slots(self._energy_demand_kWh, last_time_slot)
        self._delete_time_slots(self._min_energy_demand_kWh, last_time_slot)
        self._delete_time_slots(self._max_energy_demand_kWh, last_time_slot)
        self._delete_time_slots(self._heat_demand_kJ, last_time_slot)

    def increase_total_traded_energy_kWh(self, energy_kWh: float):
        """Add to the total traded energy of the heatpump for a given time slot."""
        self._total_traded_energy_kWh += energy_kWh

    def get_state(self) -> dict:
        """Return the state."""
        return {
            "soc": convert_pendulum_to_str_in_dict(self._soc),
            "cop": convert_pendulum_to_str_in_dict(self._cop),
            "energy_demand_kWh": convert_pendulum_to_str_in_dict(self._energy_demand_kWh),
            "min_energy_demand_kWh": convert_pendulum_to_str_in_dict(self._min_energy_demand_kWh),
            "max_energy_demand_kWh": convert_pendulum_to_str_in_dict(self._max_energy_demand_kWh),
            "total_traded_energy_kWh": self._total_traded_energy_kWh,
            "total_charge_energy_kWh": self._total_charged_energy_kWh,
        }

    def restore_state(self, state_dict: dict):
        """Restore the state."""
        self._soc = convert_str_to_pendulum_in_dict(state_dict["soc"])
        self._cop = convert_str_to_pendulum_in_dict(state_dict["cop"])
        self._energy_demand_kWh = convert_str_to_pendulum_in_dict(state_dict["energy_demand_kWh"])
        self._min_energy_demand_kWh = convert_str_to_pendulum_in_dict(
            state_dict["min_energy_demand_kWh"]
        )
        self._max_energy_demand_kWh = convert_str_to_pendulum_in_dict(
            state_dict["max_energy_demand_kWh"]
        )
        self._total_traded_energy_kWh = state_dict["total_traded_energy_kWh"]
        self._total_charged_energy_kWh = state_dict["total_charge_energy_kWh"]

    def get_results_dict(self, current_time_slot: DateTime) -> dict:
        """Return the results of the given time slot."""
        return {
            "cop": self.get_cop(current_time_slot),
            "total_traded_energy_kWh": self._total_traded_energy_kWh,
            "heat_demand_kJ": self.get_heat_demand_kJ(current_time_slot),
            "soc": self.get_soc(current_time_slot),
            "total_charge_energy_kWh": self._total_charged_energy_kWh,
        }


class SorTesTankEnergyParameters:
    """Energy Parameters for the SorTes Tank heat pump"""

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        heat_demand_Q_profile: Union[str, float, dict],
        ambient_temp_C_profile: Union[str, float, dict],
        target_temp_C_profile: Union[str, float, dict],
        average_trade_rate: Union[str, float, dict],
        source_type: HeatPumpSourceType = ConstSettings.HeatPumpSettings.SOURCE_TYPE,
    ):
        # pylint: disable=too-many-arguments, too-many-positional-arguments
        self._state = SorTesTankState()

        self._heat_demand_Q_J: StrategyProfileBase = profile_factory(
            heat_demand_Q_profile, None, profile_type=InputProfileTypes.IDENTITY
        )
        self._ambient_temp_C: StrategyProfileBase = profile_factory(
            ambient_temp_C_profile, None, profile_type=InputProfileTypes.IDENTITY
        )
        self._target_temp_C: StrategyProfileBase = profile_factory(
            target_temp_C_profile, None, profile_type=InputProfileTypes.IDENTITY
        )
        self._capacity_kWh: float = SorTesConfiguration.CAPACITY_KWH
        self._cop_model = cop_model_factory(COPModelType.UNIVERSAL, source_type)
        self._bought_energy_kWh = 0.0

        self._soc_management = SorTesTankMinimiseSwitchStrategy(self, average_trade_rate)

    @property
    def state(self) -> SorTesTankState:
        """Return the state."""
        return self._state

    @property
    def soc_management(self) -> SorTesTankMinimiseSwitchStrategy:
        """Return the soc management."""
        return self._soc_management

    def event_market_cycle(self, current_time_slot: DateTime):
        """Runs on market_cycle event."""
        # Order matters here
        self._soc_management.event_market_slot()
        self._rotate_profiles(current_time_slot)
        self._populate_state(current_time_slot)

    def event_activate(self):
        """Runs on activate event."""
        self._soc_management.event_activate()
        self._rotate_profiles()
        self._state.activate()

    def event_traded_energy(self, time_slot: DateTime, energy_kWh: float):
        """React to an event_traded_energy."""
        self._bought_energy_kWh += energy_kWh
        self._decrement_posted_energy(time_slot, energy_kWh)

    def get_soc(self, time_slot: DateTime):
        """Return the soc of the SorTes tank"""
        return self._state.get_soc(time_slot)

    def get_energy_demand_kWh(self, time_slot: DateTime):
        """Return the energy_demand kWh."""
        return self._state.get_energy_demand_kWh(time_slot)

    def get_min_energy_demand_kWh(self, time_slot: DateTime):
        """Return the min_energy_demand kWh."""
        return self._state.get_min_energy_demand_kWh(time_slot)

    def get_max_energy_demand_kWh(self, time_slot: DateTime):
        """Return the max_energy_demand kWh."""
        return self._state.get_max_energy_demand_kWh(time_slot)

    def _populate_state(self, time_slot: DateTime):
        # order matters!
        self._update_last_time_slot_data(time_slot)
        self._calc_and_set_cop(time_slot)
        self._state.set_heat_demand_kJ(
            time_slot, self._heat_demand_Q_J.get_value(time_slot) / 1000.0
        )
        self._calc_and_set_energy_demand(time_slot)

    def _calc_and_set_cop(self, time_slot: DateTime):
        cop = self._cop_model.calc_cop(
            source_temp_C=self._ambient_temp_C.get_value(time_slot),
            condenser_temp_C=self._target_temp_C.get_value(time_slot),
        )
        self._state.set_cop(time_slot, cop)

    def _decrement_posted_energy(self, time_slot: DateTime, energy_kWh: float):
        updated_energy_demand_kWh = max(0.0, self.get_energy_demand_kWh(time_slot) - energy_kWh)
        updated_min_energy_demand_kWh = max(
            0.0, self.get_min_energy_demand_kWh(time_slot) - energy_kWh
        )
        updated_max_energy_demand_kWh = max(
            0.0, self.get_max_energy_demand_kWh(time_slot) - energy_kWh
        )
        self._state.set_energy_demand_kWh(time_slot, updated_energy_demand_kWh)
        self._state.set_min_energy_demand_kWh(time_slot, updated_min_energy_demand_kWh)
        self._state.set_max_energy_demand_kWh(time_slot, updated_max_energy_demand_kWh)

        self._state.increase_total_traded_energy_kWh(energy_kWh)

    def _calc_and_set_energy_demand(self, time_slot: DateTime):
        energy_demand_kWh = convert_kJ_to_kWh(
            self._heat_demand_Q_J.get_value(time_slot) / 1000
        ) / self._state.get_cop(time_slot)
        self._state.set_energy_demand_kWh(time_slot, energy_demand_kWh)
        self._state.set_min_energy_demand_kWh(
            time_slot, self._calc_energy_to_buy_minimum(time_slot)
        )
        self._state.set_max_energy_demand_kWh(
            time_slot, self._calc_energy_to_buy_maximum(time_slot)
        )

    def _get_performance_energy_charge_kWh(self, time_slot: DateTime) -> float:
        charge_power_kW = SorTesPerformanceMaps.get_power_charging(
            self._ambient_temp_C.get_value(time_slot)
            + SorTesConfiguration.AMBIENT_TEMPERATURE_CORRECTION
        )
        return convert_kW_to_kWh(charge_power_kW, GlobalConfig.slot_length)

    def _get_performance_energy_discharge_kWh(self, time_slot: DateTime) -> float:
        discharge_power_kW = SorTesPerformanceMaps.get_power_discharging(
            self._ambient_temp_C.get_value(time_slot)
            - SorTesConfiguration.AMBIENT_TEMPERATURE_CORRECTION
        )
        return convert_kW_to_kWh(discharge_power_kW, GlobalConfig.slot_length)

    def _calc_condenser_electricity_kWh(self, charging_energy_kWh: float) -> float:
        return (
            charging_energy_kWh
            / SorTesConfiguration.COP_CONDENSER
            * SorTesConfiguration.CONVERSION_CHARGE_CONDENSER_POWER
        )

    def _calc_evaporator_electricity_kWh(self, discharging_energy_kWh: float) -> float:
        return (
            discharging_energy_kWh
            / SorTesConfiguration.COP_EVAPORATOR
            * SorTesConfiguration.CONVERSION_DISCHARGE_EVAPORATOR_POWER
        )

    def _get_total_electricity_demand_for_time_slot_kWh(self, time_slot: DateTime) -> float:
        # we need this function in order to also access the demand after trading
        return convert_kJ_to_kWh(self._state.get_heat_demand_kJ(time_slot)) / self._state.get_cop(
            time_slot
        )

    def _calc_heat_capacity_into_electricity_kWh(self, heat_capacity: float) -> float:
        return heat_capacity / SorTesConfiguration.COP_HEAT_SOURCE

    def _calc_available_free_storage_kWh(self, time_slot: DateTime) -> float:
        charge_energy_kWh = self._get_performance_energy_charge_kWh(time_slot)
        # add the charge energy to the capacity be able to reach the maximum SOC tolerance
        available_heat_storage_kWh = (
            (SorTesConfiguration.MAX_SOC_TOLERANCE - self._state.get_soc(time_slot)) / 100
        ) * self._capacity_kWh + charge_energy_kWh

        if available_heat_storage_kWh < charge_energy_kWh:
            return 0
        return charge_energy_kWh

    def _calc_available_stored_heat_kWh(self, time_slot: DateTime) -> float:
        discharge_energy_kWh = self._get_performance_energy_discharge_kWh(time_slot)
        # add the discharge energy to the capacity be able to reach the minimum SOC tolerance
        stored_heat_kWh = (
            (self._state.get_soc(time_slot) - SorTesConfiguration.MIN_SOC_TOLERANCE) / 100
        ) * self._capacity_kWh + discharge_energy_kWh

        if stored_heat_kWh < discharge_energy_kWh:
            return 0
        return discharge_energy_kWh

    def _calc_energy_to_buy_maximum(self, time_slot: DateTime) -> float:
        available_heat_storage_kWh = self._calc_available_free_storage_kWh(time_slot)
        return (
            self._get_total_electricity_demand_for_time_slot_kWh(time_slot)
            + self._calc_heat_capacity_into_electricity_kWh(available_heat_storage_kWh)
            + self._calc_condenser_electricity_kWh(available_heat_storage_kWh)
        )

    def _calc_energy_to_buy_minimum(self, time_slot: DateTime) -> float:
        available_stored_heat_kWh = self._calc_available_stored_heat_kWh(time_slot)
        electricity_demand_kWh = self._get_total_electricity_demand_for_time_slot_kWh(time_slot)
        energy_to_be_bought_for_heat = (
            electricity_demand_kWh
            - self._calc_heat_capacity_into_electricity_kWh(available_stored_heat_kWh)
        )

        if energy_to_be_bought_for_heat < FLOATING_POINT_TOLERANCE:
            # corner case when the demand is lower than the discharging energy
            log.warning(
                "The heat demand is lower than the discharging energy: %s, %s",
                self._get_total_electricity_demand_for_time_slot_kWh(time_slot),
                self._calc_heat_capacity_into_electricity_kWh(available_stored_heat_kWh),
            )
            return electricity_demand_kWh

        return energy_to_be_bought_for_heat + self._calc_evaporator_electricity_kWh(
            available_stored_heat_kWh
        )

    def _rotate_profiles(self, time_slot: Optional[DateTime] = None):
        self._state.delete_past_state_values(time_slot)
        self._heat_demand_Q_J.read_or_rotate_profiles()
        self._ambient_temp_C.read_or_rotate_profiles()
        self._target_temp_C.read_or_rotate_profiles()

    def _charge_or_discharge_tank(self, time_slot: DateTime):
        electricity_demand_kWh = self._get_total_electricity_demand_for_time_slot_kWh(
            self.last_time_slot(time_slot)
        )
        net_traded_energy_kWh = self._bought_energy_kWh - electricity_demand_kWh

        def _is_net_traded_energy_zero():
            return isclose(net_traded_energy_kWh, 0, abs_tol=FLOATING_POINT_TOLERANCE)

        if _is_net_traded_energy_zero():
            self._no_charge(time_slot)
            return

        if (
            self.soc_management.current_state == HeatPumpChargingState.CHARGE
            and net_traded_energy_kWh > FLOATING_POINT_TOLERANCE
        ):
            self._charge(net_traded_energy_kWh, time_slot)
        elif self.soc_management.current_state == HeatPumpChargingState.DISCHARGE:
            self._discharge(net_traded_energy_kWh, time_slot)
        else:
            assert False, "should never reach this point"

    def _charge(self, net_traded_energy_kWh: float, time_slot: DateTime):
        charge_energy_kWh = self._get_performance_energy_charge_kWh(self.last_time_slot(time_slot))
        condenser_energy_kWh = self._calc_condenser_electricity_kWh(charge_energy_kWh)
        heat_energy_kWh = net_traded_energy_kWh * SorTesConfiguration.COP_HEAT_SOURCE
        assert (
            abs(condenser_energy_kWh + charge_energy_kWh - heat_energy_kWh)
            < FLOATING_POINT_TOLERANCE
        )

        self._update_soc(time_slot, charge_energy_kWh)
        self._state.update_total_charged_energy_kWh(charge_energy_kWh)

    def _discharge(self, net_traded_energy_kWh: float, time_slot: DateTime):
        assert net_traded_energy_kWh < FLOATING_POINT_TOLERANCE
        discharge_energy_kWh = self._get_performance_energy_discharge_kWh(
            self.last_time_slot(time_slot)
        )
        evaporator_energy_kWh = self._calc_evaporator_electricity_kWh(discharge_energy_kWh)
        assert (net_traded_energy_kWh - evaporator_energy_kWh) < FLOATING_POINT_TOLERANCE

        self._update_soc(time_slot, -discharge_energy_kWh)
        self._state.update_total_charged_energy_kWh(-discharge_energy_kWh)

    def _update_soc(self, time_slot: DateTime, heat_energy_kWh: float):
        old_charge = self._state.get_soc(self.last_time_slot(time_slot)) / 100 * self._capacity_kWh
        new_charge = old_charge + heat_energy_kWh
        new_soc = new_charge / self._capacity_kWh
        self._state.set_soc(time_slot, new_soc * 100)

    def _no_charge(self, time_slot: DateTime):
        self._state.set_soc(time_slot, self._state.get_soc(self.last_time_slot(time_slot)))

    def _update_last_time_slot_data(self, time_slot: DateTime):
        last_time_slot = self.last_time_slot(time_slot)
        if last_time_slot not in self._ambient_temp_C.profile:
            return
        self._charge_or_discharge_tank(time_slot)

        self._bought_energy_kWh = 0.0

    @staticmethod
    def last_time_slot(current_market_slot: DateTime) -> DateTime:
        """Calculate the previous time slot from the current one."""
        return current_market_slot - GlobalConfig.slot_length


class HeatPumpWithSorTesTankStrategy(HeatPumpStrategyBase):
    """Strategy class for a heat pump that is connected to a SorTES tank"""

    def __init__(
        self,
        heat_demand_Q_profile: Union[str, float, dict],
        ambient_temp_C_profile: Union[str, float, dict],
        target_temp_C_profile: Union[str, float, dict],
        average_trade_rate: Union[str, float, dict],
        source_type: HeatPumpSourceType = ConstSettings.HeatPumpSettings.SOURCE_TYPE,
        order_updater_parameters: dict[
            AvailableMarketTypes, HeatPumpOrderUpdaterParameters
        ] = None,
    ):
        # pylint: disable=too-many-arguments, too-many-positional-arguments, super-init-not-called

        self._init_price_params(order_updater_parameters)

        self._energy_params = SorTesTankEnergyParameters(
            heat_demand_Q_profile=heat_demand_Q_profile,
            ambient_temp_C_profile=ambient_temp_C_profile,
            target_temp_C_profile=target_temp_C_profile,
            average_trade_rate=average_trade_rate,
            source_type=source_type,
        )

    def post_order(
        self, market: "MarketBase", market_slot: DateTime, order_rate: float = None, **kwargs
    ):
        if not order_rate:
            order_rate = self._order_updaters[market][market_slot].get_energy_rate(self.area.now)
        else:
            order_rate = Decimal(order_rate)
        order_energy_kWh = Decimal(
            self._energy_params.soc_management.calculate(market_slot, float(order_rate))
        )
        self._post_order(market, market_slot, order_energy_kWh, order_rate)

    @property
    def state(self) -> SorTesTankState:
        return self._energy_params.state

    def _init_price_params(self, order_updater_parameters):
        if not order_updater_parameters:
            order_updater_parameters = {
                AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters()
            }

        super().__init__(order_updater_parameters=order_updater_parameters)
