from enum import Enum

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.validators import StorageValidator

from gsy_e.models.state import ESSEnergyOrigin, StorageState
from gsy_e.models.strategy.scm import SCMStrategy

StorageSettings = ConstSettings.StorageSettings


class SCMStorageStrategy(SCMStrategy):
    """Storage SCM strategy."""
    # pylint: disable=too-many-arguments
    def __init__(
            self, initial_soc: float = StorageSettings.MIN_ALLOWED_SOC,
            min_allowed_soc=StorageSettings.MIN_ALLOWED_SOC,
            battery_capacity_kWh: float = StorageSettings.CAPACITY,
            max_abs_battery_power_kW: float = StorageSettings.MAX_ABS_POWER,
            initial_energy_origin: Enum = ESSEnergyOrigin.EXTERNAL):
        StorageValidator.validate(
            initial_soc=initial_soc, min_allowed_soc=min_allowed_soc,
            battery_capacity_kWh=battery_capacity_kWh,
            max_abs_battery_power_kW=max_abs_battery_power_kW)
        self._state = StorageState(
            initial_soc=initial_soc, initial_energy_origin=initial_energy_origin,
            capacity=battery_capacity_kWh, max_abs_battery_power_kW=max_abs_battery_power_kW,
            min_allowed_soc=min_allowed_soc)

    def activate(self, area):
        """Activate the strategy."""
        self._state.add_default_values_to_state_profiles([area.current_market_time_slot])
        self._state.activate(
            area.simulation_config.slot_length,
            area.current_market_time_slot
            if area.current_market_time_slot else area.config.start_date)

    def market_cycle(self, area):
        """Update the storage state for the next time slot."""
        self._state.add_default_values_to_state_profiles([area.current_market_time_slot])
        self._state.market_cycle(area.past_market_time_slot, area.current_market_time_slot, [])
        self._state.delete_past_state_values(area.past_market_time_slot)
        self._state.check_state(area.current_market_time_slot)

    def get_available_energy_to_sell_kWh(self, time_slot):
        """Get the available energy for production for the specified time slot."""
        return self._state.get_available_energy_to_sell_kWh(time_slot)

    def get_available_energy_to_buy_kWh(self, time_slot):
        """Get the available energy for consumption for the specified time slot."""
        return self._state.get_available_energy_to_buy_kWh(time_slot)
