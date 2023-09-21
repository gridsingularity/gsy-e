from enum import Enum
from typing import Dict, TYPE_CHECKING

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.validators import StorageValidator
from gsy_framework.utils import key_in_dict_and_not_none
from pendulum import DateTime

from gsy_e.models.strategy.state import ESSEnergyOrigin, StorageState
from gsy_e.models.strategy.scm import SCMStrategy

StorageSettings = ConstSettings.StorageSettings


if TYPE_CHECKING:
    from gsy_e.models.area import AreaBase, CoefficientArea


class SCMStorageStrategy(SCMStrategy):
    """Storage SCM strategy."""
    # pylint: disable=too-many-arguments
    def __init__(
            self, initial_soc: float = StorageSettings.MIN_ALLOWED_SOC,
            min_allowed_soc=StorageSettings.MIN_ALLOWED_SOC,
            battery_capacity_kWh: float = StorageSettings.CAPACITY,
            max_abs_battery_power_kW: float = StorageSettings.MAX_ABS_POWER,
            initial_energy_origin: Enum = ESSEnergyOrigin.EXTERNAL):
        self._initial_soc = initial_soc
        self._min_allowed_soc = min_allowed_soc
        self._battery_capacity_kWh = battery_capacity_kWh
        self._max_abs_battery_power_kW = max_abs_battery_power_kW
        self._initial_energy_origin = initial_energy_origin

        self._validate_and_init_state()

    @property
    def state(self):
        return self._state

    def serialize(self) -> Dict:
        """Serialize the strategy parameters."""
        return {
            "initial_soc": self._state.initial_soc,
            "min_allowed_soc": self._state.min_allowed_soc_ratio * 100.0,
            "battery_capacity_kWh": self._state.capacity,
            "max_abs_battery_power_kW": self._state.max_abs_battery_power_kW,
            "initial_energy_origin": self._state.initial_energy_origin,
        }

    def activate(self, area: "AreaBase") -> None:
        """Activate the strategy."""
        self._state.add_default_values_to_state_profiles([area.current_market_time_slot])
        self._state.activate(
            area.config.slot_length,
            area.current_market_time_slot
            if area.current_market_time_slot else area.config.start_date)

    def market_cycle(self, area: "AreaBase") -> None:
        """Update the storage state for the next time slot."""
        self._state.add_default_values_to_state_profiles([area.current_market_time_slot])
        self._state.market_cycle(area.past_market_time_slot, area.current_market_time_slot, [])
        self._state.delete_past_state_values(area.past_market_time_slot)
        self._state.check_state(area.current_market_time_slot)

    def get_energy_to_sell_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for production for the specified time slot."""
        return self._state.get_available_energy_to_sell_kWh(time_slot)

    def get_energy_to_buy_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for consumption for the specified time slot."""
        return self._state.get_available_energy_to_buy_kWh(time_slot)

    def decrease_energy_to_sell(
            self, traded_energy_kWh: float, time_slot: DateTime, area: "CoefficientArea"):
        """Decrease traded energy from the state and the strategy parameters."""
        self._state.register_energy_from_offer_trade(traded_energy_kWh, time_slot)

    def decrease_energy_to_buy(
            self, traded_energy_kWh: float, time_slot: DateTime, area: "CoefficientArea"):
        """Decrease traded energy from the state and the strategy parameters."""
        self._state.register_energy_from_bid_trade(traded_energy_kWh, time_slot)

    def area_reconfigure_event(self, **kwargs):
        altered = False
        if key_in_dict_and_not_none(kwargs, "battery_capacity_kWh"):
            self._battery_capacity_kWh = kwargs["battery_capacity_kWh"]
            altered = True
        if key_in_dict_and_not_none(kwargs, "min_allowed_soc"):
            self._min_allowed_soc = kwargs["min_allowed_soc"]
            altered = True
        if key_in_dict_and_not_none(kwargs, "max_abs_battery_power_kW"):
            self._max_abs_battery_power_kW = kwargs["max_abs_battery_power_kW"]
            altered = True
        if altered:
            self._validate_and_init_state()

    def _validate_and_init_state(self):
        StorageValidator.validate(
            initial_soc=self._initial_soc, min_allowed_soc=self._min_allowed_soc,
            battery_capacity_kWh=self._battery_capacity_kWh,
            max_abs_battery_power_kW=self._max_abs_battery_power_kW)
        self._state = StorageState(
            initial_soc=self._initial_soc, initial_energy_origin=self._initial_energy_origin,
            capacity=self._battery_capacity_kWh,
            max_abs_battery_power_kW=self._max_abs_battery_power_kW,
            min_allowed_soc=self._min_allowed_soc)
