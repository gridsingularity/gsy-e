from abc import ABC, abstractmethod
from enum import Enum
from statistics import mean
from typing import Optional, TYPE_CHECKING

from gsy_framework.constants_limits import GlobalConfig
from pendulum import DateTime, duration

import gsy_e.constants

if TYPE_CHECKING:
    from gsy_e.models.strategy.energy_parameters.heatpump.heat_pump import HeatPumpEnergyParameters


class HeatPumpSOCManagement(ABC):
    """Abstract base class for all heat pump SOC management classes."""

    def event_activate(self):
        """Base method for the activate event"""

    @abstractmethod
    def calculate(self, time_slot: DateTime, buy_rate: float) -> float:
        """Calculate the energy that should be placed as a bid by the heat pump."""


class HeatPumpPreferredBuyingRateStrategy(HeatPumpSOCManagement):
    """
    Strategy class for managing the SOC of the heat storage based on a preferred buying rate.
    """

    def __init__(self, energy_params: "HeatPumpEnergyParameters", preferred_buying_rate: float):
        self._preferred_buying_rate = preferred_buying_rate
        self._energy_params = energy_params

    def calculate(self, time_slot: DateTime, buy_rate: float) -> float:
        """
        Calculate the bid energy depending on whether the current market rate exceeds the
        preferred buying rate or not.
        """
        if buy_rate > self._preferred_buying_rate:
            return self._energy_params.get_min_energy_demand_kWh(time_slot)
        return self._energy_params.get_max_energy_demand_kWh(time_slot)


class HeatPumpChargingState(Enum):
    """State of the heat pump storage."""

    DISCHARGE = 0
    CHARGE = 1
    MAINTAIN_SOC = 2


class MinimiseHeatpumpSwitchStrategy(HeatPumpSOCManagement):
    """
    Strategy class for managing the SOC of the heat storage by minimizing the number of switch on
    and off of the heat pump.
    """

    MINUTES_BEFORE_SWITCH_ALLOWED = 120
    MIN_SOC_TOLERANCE = 15
    MAX_SOC_TOLERANCE = 85

    def __init__(self, energy_params: "HeatPumpEnergyParameters"):
        self._last_switch: Optional[DateTime] = None
        self._energy_params = energy_params
        self._charger = energy_params.combined_state._charger
        self._current_state = HeatPumpChargingState.CHARGE
        self._average_rate = None

    def event_activate(self):
        if isinstance(GlobalConfig.market_maker_rate, dict):
            self._average_rate = mean(GlobalConfig.market_maker_rate.values())
        else:
            assert False, "GlobalConfig.market_maker_rate was not initiated yet."

    def calculate(self, time_slot: DateTime, _buy_rate: float = 0.0):
        """
        Calculate the bid energy depending on the current state of the heat pump, the current SOC
        and whether the market maker rate is cheap or expensive compared to the average market
        maker rate.
        """
        target_state = self._current_state
        if not self._is_time_for_state_change(time_slot):
            # If state change is not possible, but at the same time the soc is below the min or
            # above the max SOC value of the tank, then maintain the SOC.
            if self._charger.get_average_soc(time_slot) >= self.MAX_SOC_TOLERANCE:
                target_state = HeatPumpChargingState.MAINTAIN_SOC
            if self._charger.get_average_soc(time_slot) <= self.MIN_SOC_TOLERANCE:
                target_state = HeatPumpChargingState.MAINTAIN_SOC
        else:
            # If the state change is possible, check the market maker rate to set the new state
            target_state = self._should_charge_or_discharge(time_slot)
            if self._current_state != target_state:
                # If the target state is the same as the current state, do nothing. Otherwise,
                # update the current state and the last switch timestamp.
                self._current_state = target_state
                self._last_switch = time_slot

        return self._get_energy_from_target_state(target_state, time_slot)

    def _is_time_for_state_change(self, time_slot: DateTime) -> bool:
        if not self._last_switch:
            # If the last_switch has not been set yet, the simulation is starting and no switch has
            # occurred yet. Change state if needed.
            self._last_switch = time_slot
            return True
        if time_slot - self._last_switch < duration(minutes=self.MINUTES_BEFORE_SWITCH_ALLOWED):
            # If not enough time has passed since the last switch, do not allow state change.
            return False
        # Otherwise, allow the state change.
        return True

    def _get_energy_from_target_state(
        self, target_state: HeatPumpChargingState, time_slot: DateTime
    ) -> float:
        if target_state == HeatPumpChargingState.CHARGE:
            return self._energy_params.get_max_energy_demand_kWh(time_slot)
        if target_state == HeatPumpChargingState.DISCHARGE:
            return self._energy_params.get_min_energy_demand_kWh(time_slot)
        return self._energy_params.get_energy_demand_kWh(time_slot)

    def _should_charge_or_discharge(self, time_slot: DateTime) -> HeatPumpChargingState:
        if GlobalConfig.market_maker_rate[time_slot] <= self._average_rate:
            # If the market maker rate is lower than the average rate, charge except if the SOC is
            # too high.
            if self._charger.get_average_soc(time_slot) >= self.MAX_SOC_TOLERANCE:
                return HeatPumpChargingState.MAINTAIN_SOC
            return HeatPumpChargingState.CHARGE

        # If the market maker rate is higher than the average rate, discharge except if the SOC
        # is too low.
        if self._charger.get_average_soc(time_slot) > self.MIN_SOC_TOLERANCE:
            return HeatPumpChargingState.DISCHARGE
        return HeatPumpChargingState.MAINTAIN_SOC


def heat_pump_soc_management_factory(
    energy_params: "HeatPumpEnergyParameters", preferred_buying_rate: float
):
    """Factory class for selecting the SOC management strategy based on the constant value."""
    if (
        gsy_e.constants.HEAT_PUMP_SOC_MANAGEMENT_ALGORITHM
        == gsy_e.constants.HeatPumpSOCManagementAlgorithm.PREFERRED_BUYING_RATE
    ):
        return HeatPumpPreferredBuyingRateStrategy(energy_params, preferred_buying_rate)
    return MinimiseHeatpumpSwitchStrategy(energy_params)
