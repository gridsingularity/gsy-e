"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from abc import ABC, abstractmethod
from collections import namedtuple
from enum import Enum
from math import isclose, copysign
from typing import Dict, Optional, List

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.utils import (
    convert_pendulum_to_str_in_dict, convert_str_to_pendulum_in_dict, convert_kW_to_kWh,
    limit_float_precision)
from pendulum import DateTime

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.gsy_e_core.util import is_time_slot_in_past_markets, write_default_to_dict

StorageSettings = ConstSettings.StorageSettings


# Complex device models should be split in three classes each:
#
# - a strategy class responsible for buying/selling options
# - an appliance class responsible for actual energy transfers (drawing/serving options)
#   (appliance class has to be reinstated if needed)
# - a state class keeping the state of the appliance
#
# The full three-classes setup is not necessary for every device:
# - Some devices may not have a state. The state class is mainly meant to share data between
#   strategy and appliance, so simple responses to triggers and events are not part of it,
#   neither are unpredictable parameters that the strategy can not take into account
# - If a device has no state, maybe it doesn't need its own appliance class either


class StateInterface(ABC):
    """Interface containing methods that need to be defined by each State class."""

    @abstractmethod
    def get_state(self) -> Dict:
        """Return the current state of the device."""
        return {}

    @abstractmethod
    def restore_state(self, state_dict: Dict):
        """Update the state of the device using the provided dictionary."""

    @abstractmethod
    def delete_past_state_values(self, current_time_slot: DateTime):
        """Delete the state of the device before the given time slot."""

    def __str__(self):
        return self.__class__.__name__


class ProsumptionInterface(StateInterface, ABC):
    """Interface with common methods/variables shared by consumption and production devices."""

    def __init__(self):
        # Actual energy consumed/produced by the device at specific market slots
        self._energy_measurement_kWh: Dict[DateTime, float] = {}
        self._unsettled_deviation_kWh: Dict[DateTime, float] = {}
        self._forecast_measurement_deviation_kWh: Dict[DateTime, float] = {}

    # pylint: disable=unused-argument, no-self-use
    def _calculate_unsettled_energy_kWh(
            self, measured_energy_kWh: float, time_slot: DateTime) -> float:
        """
        Calculates the unsettled energy (produced or consumed) in kWh.
        Args:
            measured_energy_kWh: Energy measurement, in kWh
            time_slot: Time slot that the energy measurement refers to

        Returns: Float value for the kWh of unsettled energy for the asset

        """
        return 0.0

    def set_energy_measurement_kWh(self, energy_kWh: float, time_slot: DateTime) -> None:
        """
        Set the actual energy consumed/produced by the device in the given market slot.
        Args:
            energy_kWh: Energy measurement, in kWh
            time_slot: Time slot that the energy measurement refers to

        Returns: None

        """
        self._energy_measurement_kWh[time_slot] = energy_kWh
        self._forecast_measurement_deviation_kWh[time_slot] = self._calculate_unsettled_energy_kWh(
            energy_kWh, time_slot)
        self._unsettled_deviation_kWh[time_slot] = (
            abs(self._forecast_measurement_deviation_kWh[time_slot]))

    def get_energy_measurement_kWh(self, time_slot: DateTime) -> float:
        """
        Get the actual energy consumed/produced by the device in the given market slot.
        Args:
            time_slot: Time slot that the energy measurement refers to

        Returns: Energy measurement value in kWh

        """
        return self._energy_measurement_kWh.get(time_slot)

    def get_forecast_measurement_deviation_kWh(self, time_slot: DateTime) -> float:
        """
        Get the energy deviation of forecasted energy from measurement by the device in
        the given market slot. Negative value means that the deviation is beneficial to the
        grid (and can be posted as an offer), positive value means that the deviation is
        detrimental to the grid (and can be posted as a bid)
        Args:
            time_slot: Time slot that the energy forecast/measurement refers to

        Returns: Deviation between the forecast and measurement for this time_slot, in kWh

        """
        return self._forecast_measurement_deviation_kWh.get(time_slot)

    def can_post_settlement_bid(self, time_slot: DateTime) -> bool:
        """
        Checks whether a settlement bid should be posted
        Args:
            time_slot:  Time slot that the bid should be posted

        Returns: True if the bid should be posted, false otherwise

        """
        return self._forecast_measurement_deviation_kWh.get(time_slot, 0.0) > 0.0

    def can_post_settlement_offer(self, time_slot: DateTime) -> bool:
        """
        Checks whether a settlement offer should be posted
        Args:
            time_slot:  Time slot that the offer should be posted

        Returns: True if the offer should be posted, false otherwise

        """
        return self._forecast_measurement_deviation_kWh.get(time_slot, 0.0) < 0.0

    def get_unsettled_deviation_kWh(self, time_slot: DateTime) -> float:
        """
        Get the unsettled energy deviation of forecasted energy from measurement by the device
        in the given market slot.
        Args:
            time_slot: Time slot of the unsettled deviation

        Returns: Unsettled energy deviation, in kWh

        """
        return self._unsettled_deviation_kWh.get(time_slot)

    def get_signed_unsettled_deviation_kWh(
            self, time_slot: DateTime) -> Optional[float]:
        """
        Get the unsettled energy deviation of forecasted energy from measurement by the device
        in the given market slot including the correct sign that shows the direction
        of the deviation.
        Args:
            time_slot: Time slot of the unsettled deviation

        Returns: Unsettled energy deviation, in kWh

        """
        unsettled_deviation = self._unsettled_deviation_kWh.get(time_slot)
        forecast_measurement_deviation = self._forecast_measurement_deviation_kWh.get(time_slot)
        if unsettled_deviation and forecast_measurement_deviation:
            return copysign(unsettled_deviation, forecast_measurement_deviation)
        return None

    def decrement_unsettled_deviation(
            self, purchased_energy_kWh: float, time_slot: DateTime) -> None:
        """
        Decrease the device unsettled energy in a specific market slot.
        Args:
            purchased_energy_kWh: Settled energy that should be decremented from the unsettled
            time_slot: Time slot of the unsettled energy

        Returns: None

        """
        self._unsettled_deviation_kWh[time_slot] -= purchased_energy_kWh
        assert self._unsettled_deviation_kWh[time_slot] >= -FLOATING_POINT_TOLERANCE, (
            f"Unsettled energy deviation fell below zero "
            f"({self._unsettled_deviation_kWh[time_slot]}).")


class ConsumptionState(ProsumptionInterface):
    """State for devices that can consume energy."""

    def __init__(self):
        super().__init__()
        # Energy that the load wants to consume (given by the profile or live energy requirements)
        self._desired_energy_Wh: Dict = {}
        # Energy that the load needs to consume. It's reduced when new energy is bought
        self._energy_requirement_Wh: Dict = {}
        self._total_energy_demanded_Wh: int = 0

    def get_state(self) -> Dict:
        """Return the current state of the device. Extends super implementation."""
        state = super().get_state()
        consumption_state = {
            "desired_energy_Wh": convert_pendulum_to_str_in_dict(self._desired_energy_Wh),
            "total_energy_demanded_Wh": self._total_energy_demanded_Wh}
        # The inherited state should not have keys with the same name (to avoid overwriting them)
        conflicting_keys = state.keys() & consumption_state.keys()
        assert not conflicting_keys, f"Conflicting state values found for {conflicting_keys}."

        state.update(consumption_state)
        return state

    def restore_state(self, state_dict: Dict):
        super().restore_state(state_dict)

        self._desired_energy_Wh.update(convert_str_to_pendulum_in_dict(
            state_dict["desired_energy_Wh"]))
        self._total_energy_demanded_Wh = state_dict["total_energy_demanded_Wh"]

    def get_energy_requirement_Wh(self, time_slot: DateTime, default_value: float = 0.0) -> float:
        """Return the energy requirement in a specific time_slot."""
        return self._energy_requirement_Wh.get(time_slot, default_value)

    def set_desired_energy(self, energy: float, time_slot: DateTime, overwrite=False) -> None:
        """Set the energy_requirement_Wh and desired_energy_Wh in a specific time_slot."""
        if overwrite is False and time_slot in self._energy_requirement_Wh:
            return
        self._energy_requirement_Wh[time_slot] = energy
        self._desired_energy_Wh[time_slot] = energy

    def update_total_demanded_energy(self, time_slot: DateTime) -> None:
        """Accumulate the _total_energy_demanded_Wh based on the desired energy per time_slot."""
        self._total_energy_demanded_Wh += self._desired_energy_Wh.get(time_slot, 0.)

    def can_buy_more_energy(self, time_slot: DateTime) -> bool:
        """Check whether the consumer can but more energy in the passed time_slot."""
        if time_slot not in self._energy_requirement_Wh:
            return False

        return self._energy_requirement_Wh[time_slot] > FLOATING_POINT_TOLERANCE

    def calculate_energy_to_accept(self, offer_energy_Wh: float, time_slot: DateTime) -> float:
        """Return the amount of energy that can be accepted in a specific market slot.

        The acceptable energy can't be more than the total energy required in that slot.
        """
        return min(offer_energy_Wh, self._energy_requirement_Wh[time_slot])

    def decrement_energy_requirement(
            self, purchased_energy_Wh: float, time_slot: DateTime, area_name: str) -> None:
        """Decrease the energy required by the device in a specific market slot."""
        self._energy_requirement_Wh[time_slot] -= purchased_energy_Wh
        assert self._energy_requirement_Wh[time_slot] >= -FLOATING_POINT_TOLERANCE, (
            f"Energy requirement for device {area_name} fell below zero "
            f"({self._energy_requirement_Wh[time_slot]}).")

    def delete_past_state_values(self, current_time_slot: DateTime):
        """Delete data regarding energy consumption for past market slots."""
        to_delete = []
        for market_slot in self._energy_requirement_Wh:
            if is_time_slot_in_past_markets(market_slot, current_time_slot):
                to_delete.append(market_slot)

        for market_slot in to_delete:
            self._energy_requirement_Wh.pop(market_slot, None)
            self._desired_energy_Wh.pop(market_slot, None)

    def get_desired_energy_Wh(self, time_slot, default_value=0.0):
        """Return the expected consumed energy at a specific market slot."""
        return self._desired_energy_Wh.get(time_slot, default_value)


class ProductionState(ProsumptionInterface):
    """State for devices that can produce energy."""

    def __init__(self):
        super().__init__()
        self._available_energy_kWh = {}
        self._energy_production_forecast_kWh = {}

    def get_state(self) -> Dict:
        """Return the current state of the device. Extends super implementation."""
        state = super().get_state()
        production_state = {
            "available_energy_kWh": convert_pendulum_to_str_in_dict(self._available_energy_kWh),
            "energy_production_forecast_kWh":
                convert_pendulum_to_str_in_dict(self._energy_production_forecast_kWh)}
        # The inherited state should not have keys with the same name (to avoid overwriting them)
        conflicting_keys = state.keys() & production_state.keys()
        assert not conflicting_keys, f"Conflicting state values found for {conflicting_keys}."

        state.update(production_state)
        return state

    def restore_state(self, state_dict: Dict):
        """Update the state of the device using the provided dictionary."""
        super().restore_state(state_dict)

        self._available_energy_kWh.update(
            convert_str_to_pendulum_in_dict(state_dict["available_energy_kWh"]))
        self._energy_production_forecast_kWh.update(
            convert_str_to_pendulum_in_dict(state_dict["energy_production_forecast_kWh"]))

    def set_available_energy(self, energy_kWh: float, time_slot: DateTime,
                             overwrite: bool = False) -> None:
        """Set the available energy in the passed time_slot.

        If overwrite is True, set the available energy even if the time_slot is already tracked.
        """
        if overwrite is False and time_slot in self._energy_production_forecast_kWh:
            return
        self._energy_production_forecast_kWh[time_slot] = energy_kWh
        self._available_energy_kWh[time_slot] = energy_kWh

        assert self._energy_production_forecast_kWh[time_slot] >= 0.0

    def get_available_energy_kWh(self, time_slot: DateTime, default_value: float = 0.0) -> float:
        """Return the available energy in a specific time_slot."""
        available_energy = self._available_energy_kWh.get(time_slot, default_value)

        assert available_energy >= -FLOATING_POINT_TOLERANCE
        return available_energy

    def decrement_available_energy(self, sold_energy_kWh: float, time_slot: DateTime,
                                   area_name: str) -> None:
        """Decrement the available energy after a successful trade."""
        self._available_energy_kWh[time_slot] -= sold_energy_kWh
        assert self._available_energy_kWh[time_slot] >= -FLOATING_POINT_TOLERANCE, (
            f"Available energy for device {area_name} fell below zero "
            f"({self._available_energy_kWh[time_slot]}).")

    def delete_past_state_values(self, current_time_slot: DateTime):
        """Delete data regarding energy production for past market slots."""
        to_delete = []
        for market_slot in self._available_energy_kWh:
            if is_time_slot_in_past_markets(market_slot, current_time_slot):
                to_delete.append(market_slot)

        for market_slot in to_delete:
            self._available_energy_kWh.pop(market_slot, None)
            self._energy_production_forecast_kWh.pop(market_slot, None)

    def get_energy_production_forecast_kWh(self, time_slot: DateTime, default_value: float = 0.0):
        """Return the expected produced energy at a specific market slot."""
        production_forecast = self._energy_production_forecast_kWh.get(time_slot, default_value)
        assert production_forecast >= -FLOATING_POINT_TOLERANCE

        return production_forecast


class PVState(ProductionState):
    """State class for PV devices.

    Completely inherits ProductionState, but we keep this class for backward compatibility.
    """

    def _calculate_unsettled_energy_kWh(
            self, measured_energy_kWh: float, time_slot: DateTime) -> float:
        """
        Returns negative values for overproduction (offer will be placed on the settlement market)
        and positive values for underproduction (bid will be placed on the settlement market)
        :param measured_energy_kWh: Measured energy that the PV produced
        :param time_slot: time slot of the measured energy
        :return: Deviation between forecasted and measured energy
        """
        traded_energy_kWh = (self.get_energy_production_forecast_kWh(time_slot) -
                             self.get_available_energy_kWh(time_slot))
        return traded_energy_kWh - measured_energy_kWh


class LoadState(ConsumptionState):
    """State for the load asset."""

    @property
    def total_energy_demanded_Wh(self) -> float:
        """Return the total energy demanded in Wh."""
        return self._total_energy_demanded_Wh

    def get_desired_energy(self, time_slot: DateTime) -> float:
        """Return the desired energy (based on profile data)."""
        return self._desired_energy_Wh[time_slot]

    def _calculate_unsettled_energy_kWh(
            self, measured_energy_kWh: float, time_slot: DateTime) -> float:
        """
        Returns negative values for underconsumption (offer will be placed on the settlement
        market) and positive values for overconsumption (bid will be placed on the settlement
        market)
        :param measured_energy_kWh: Measured energy that the load produced
        :param time_slot: time slot of the measured energy
        :return: Deviation between forecasted and measured energy
        """
        traded_energy_kWh = (self.get_desired_energy_Wh(time_slot) -
                             self.get_energy_requirement_Wh(time_slot)) / 1000.0
        return measured_energy_kWh - traded_energy_kWh


class SmartMeterState(ConsumptionState, ProductionState):
    """State for the Smart Meter device."""

    @property
    def market_slots(self):
        """Return the market slots that have either available or required energy."""
        return self._available_energy_kWh.keys() | self._energy_requirement_Wh.keys()

    def delete_past_state_values(self, current_time_slot: DateTime):
        """Delete data regarding energy requirements and availability for past market slots."""
        to_delete = []
        for market_slot in self.market_slots:
            if is_time_slot_in_past_markets(market_slot, current_time_slot):
                to_delete.append(market_slot)

        for market_slot in to_delete:
            self._available_energy_kWh.pop(market_slot, None)
            self._energy_production_forecast_kWh.pop(market_slot, None)
            self._energy_requirement_Wh.pop(market_slot, None)
            self._desired_energy_Wh.pop(market_slot, None)

    def get_energy_at_market_slot(self, time_slot: DateTime) -> float:
        """Return the energy produced/consumed by the device at a specific market slot (in kWh).

        NOTE: The returned energy can either be negative (production) or positive (consumption).
        Therefore, pay attention when using its return values for strategy computations.
        """
        # We want the production energy to be a negative number (that's standard practice)
        produced_energy_kWh = -(abs(self.get_energy_production_forecast_kWh(time_slot, 0.0)))
        consumed_energy_kWh = self.get_desired_energy_Wh(time_slot, 0.0) / 1000
        if produced_energy_kWh and consumed_energy_kWh:
            raise UnexpectedStateException(
                f"{self} reported both produced and consumed energy at slot {time_slot}.")

        return produced_energy_kWh if produced_energy_kWh else consumed_energy_kWh


class ESSEnergyOrigin(Enum):
    """Enum for the storage's possible sources of energy."""
    LOCAL = 1
    EXTERNAL = 2
    UNKNOWN = 3


EnergyOrigin = namedtuple("EnergyOrigin", ("origin", "value"))


# pylint: disable= too-many-instance-attributes, too-many-arguments
class StorageState(StateInterface):
    """State for the storage asset."""

    def __init__(self,
                 initial_soc=StorageSettings.MIN_ALLOWED_SOC,
                 initial_energy_origin=ESSEnergyOrigin.EXTERNAL,
                 capacity=StorageSettings.CAPACITY,
                 max_abs_battery_power_kW=StorageSettings.MAX_ABS_POWER,
                 min_allowed_soc=StorageSettings.MIN_ALLOWED_SOC):

        self.initial_soc = initial_soc
        self.initial_capacity_kWh = capacity * initial_soc / 100

        self.min_allowed_soc_ratio = min_allowed_soc / 100

        self.capacity = capacity
        self.max_abs_battery_power_kW = max_abs_battery_power_kW

        # storage capacity, that is already sold:
        self.pledged_sell_kWh = {}
        # storage capacity, that has been offered (but not traded yet):
        self.offered_sell_kWh = {}
        # energy, that has been bought:
        self.pledged_buy_kWh = {}
        # energy, that the storage wants to buy (but not traded yet):
        self.offered_buy_kWh = {}
        self.time_series_ess_share = {}

        self.charge_history = {}
        self.charge_history_kWh = {}
        self.offered_history = {}
        self.used_history = {}  # type: Dict[DateTime, float]
        self.energy_to_buy_dict = {}
        self.energy_to_sell_dict = {}

        self._used_storage = self.initial_capacity_kWh
        self._battery_energy_per_slot = 0.0
        self._used_storage_share = [EnergyOrigin(initial_energy_origin, self.initial_capacity_kWh)]
        self._current_market_slot = None

    def get_state(self) -> Dict:
        return {
            "pledged_sell_kWh": convert_pendulum_to_str_in_dict(self.pledged_sell_kWh),
            "offered_sell_kWh": convert_pendulum_to_str_in_dict(self.offered_sell_kWh),
            "pledged_buy_kWh": convert_pendulum_to_str_in_dict(self.pledged_buy_kWh),
            "offered_buy_kWh": convert_pendulum_to_str_in_dict(self.offered_buy_kWh),
            "charge_history": convert_pendulum_to_str_in_dict(self.charge_history),
            "charge_history_kWh": convert_pendulum_to_str_in_dict(self.charge_history_kWh),
            "offered_history": convert_pendulum_to_str_in_dict(self.offered_history),
            "used_history": convert_pendulum_to_str_in_dict(self.used_history),
            "energy_to_buy_dict": convert_pendulum_to_str_in_dict(self.energy_to_buy_dict),
            "energy_to_sell_dict": convert_pendulum_to_str_in_dict(self.energy_to_sell_dict),
            "used_storage": self._used_storage,
            "battery_energy_per_slot": self._battery_energy_per_slot,
        }

    def restore_state(self, state_dict: Dict):
        self.pledged_sell_kWh.update(
            convert_str_to_pendulum_in_dict(state_dict["pledged_sell_kWh"]))
        self.offered_sell_kWh.update(
            convert_str_to_pendulum_in_dict(state_dict["offered_sell_kWh"]))
        self.pledged_buy_kWh.update(
            convert_str_to_pendulum_in_dict(state_dict["pledged_buy_kWh"]))
        self.offered_buy_kWh.update(
            convert_str_to_pendulum_in_dict(state_dict["offered_buy_kWh"]))
        self.charge_history.update(convert_str_to_pendulum_in_dict(state_dict["charge_history"]))
        self.charge_history_kWh.update(
            convert_str_to_pendulum_in_dict(state_dict["charge_history_kWh"]))
        self.offered_history.update(
            convert_str_to_pendulum_in_dict(state_dict["offered_history"]))
        self.used_history.update(convert_str_to_pendulum_in_dict(state_dict["used_history"]))
        self.energy_to_buy_dict.update(
            convert_str_to_pendulum_in_dict(state_dict["energy_to_buy_dict"]))
        self.energy_to_sell_dict.update(convert_str_to_pendulum_in_dict(
            state_dict["energy_to_sell_dict"]))
        self._used_storage = state_dict["used_storage"]
        self._battery_energy_per_slot = state_dict["battery_energy_per_slot"]

    @property
    def used_storage(self):
        """
        Current stored energy
        """
        return self._used_storage

    def free_storage(self, time_slot):
        """
        Storage, that has not been promised or occupied
        """
        in_use = (self._used_storage
                  - self.pledged_sell_kWh[time_slot]
                  + self.pledged_buy_kWh[time_slot])
        return self.capacity - in_use

    def _max_offer_energy_kWh(self, time_slot: DateTime) -> float:
        """Return the max tracked offered energy."""
        return (self._battery_energy_per_slot - self.pledged_sell_kWh[time_slot]
                - self.offered_sell_kWh[time_slot])

    def _max_buy_energy_kWh(self, time_slot: DateTime) -> float:
        """Return the min tracked bid energy."""
        return (self._battery_energy_per_slot - self.pledged_buy_kWh[time_slot]
                - self.offered_buy_kWh[time_slot])

    def activate(self, slot_length: int, current_time_slot: DateTime) -> None:
        """Set the battery energy in kWh per current time_slot."""
        self._battery_energy_per_slot = convert_kW_to_kWh(self.max_abs_battery_power_kW,
                                                          slot_length)
        self._current_market_slot = current_time_slot

    def _has_battery_reached_max_discharge_power(self, energy: float, time_slot: DateTime) -> bool:
        """Check whether the storage can withhold the passed energy discharge value."""
        energy_balance_kWh = abs(
            energy + self.pledged_sell_kWh[time_slot] + self.offered_sell_kWh[time_slot]
            - self.pledged_buy_kWh[time_slot] - self.offered_buy_kWh[time_slot])
        return energy_balance_kWh - self._battery_energy_per_slot > FLOATING_POINT_TOLERANCE

    def _has_battery_reached_max_charge_power(self, energy: float, time_slot: DateTime) -> bool:
        """Check whether the storage can withhold the passed energy charge value."""
        energy_balance_kWh = abs(
            energy + self.pledged_buy_kWh[time_slot] + self.offered_buy_kWh[time_slot]
            - self.pledged_sell_kWh[time_slot] - self.offered_sell_kWh[time_slot])
        return energy_balance_kWh - self._battery_energy_per_slot > FLOATING_POINT_TOLERANCE

    def _clamp_energy_to_sell_kWh(self, market_slot_time_list):
        """
        Determines available energy to sell for each active market and returns a dict[TIME, FLOAT]
        """
        accumulated_pledged = 0
        accumulated_offered = 0
        for time_slot, offered_sell_energy in self.offered_sell_kWh.items():
            if time_slot >= self._current_market_slot:
                accumulated_pledged += self.pledged_sell_kWh[time_slot]
                accumulated_offered += offered_sell_energy

        available_energy_for_all_slots = (
                self.used_storage
                - accumulated_pledged
                - accumulated_offered
                - self.min_allowed_soc_ratio * self.capacity)

        storage_dict = {}
        for time_slot in market_slot_time_list:
            if available_energy_for_all_slots < -FLOATING_POINT_TOLERANCE:
                break
            storage_dict[time_slot] = limit_float_precision(
                min(
                    available_energy_for_all_slots / len(market_slot_time_list),
                    self._max_offer_energy_kWh(time_slot),
                    self._battery_energy_per_slot)
            )
            self.energy_to_sell_dict[time_slot] = storage_dict[time_slot]
            available_energy_for_all_slots -= storage_dict[time_slot]
        return storage_dict

    def _clamp_energy_to_buy_kWh(self, market_slot_time_list):
        """
        Determines amount of energy that can be bought for each active market and writes it to
        self.energy_to_buy_dict
        """

        accumulated_bought = 0
        accumulated_sought = 0

        for time_slot, offered_buy_energy in self.offered_buy_kWh.items():
            if time_slot >= self._current_market_slot:
                accumulated_bought += self.pledged_buy_kWh[time_slot]
                accumulated_sought += offered_buy_energy
        available_energy_for_all_slots = limit_float_precision(
            (self.capacity - self.used_storage
             - accumulated_bought - accumulated_sought) / len(market_slot_time_list))

        for time_slot in market_slot_time_list:
            if available_energy_for_all_slots < -FLOATING_POINT_TOLERANCE:
                break
            clamped_energy = limit_float_precision(
                min(available_energy_for_all_slots,
                    self._max_buy_energy_kWh(time_slot),
                    self._battery_energy_per_slot))
            clamped_energy = max(clamped_energy, 0)
            self.energy_to_buy_dict[time_slot] = clamped_energy
            available_energy_for_all_slots -= clamped_energy

    def check_state(self, time_slot):
        """
        Sanity check of the state variables.
        """
        self._clamp_energy_to_sell_kWh([time_slot])
        self._clamp_energy_to_buy_kWh([time_slot])
        self._calculate_and_update_soc(time_slot)
        charge = limit_float_precision(self.used_storage / self.capacity)
        max_value = self.capacity - self.min_allowed_soc_ratio * self.capacity
        assert self.min_allowed_soc_ratio <= charge or \
            isclose(self.min_allowed_soc_ratio, charge, rel_tol=1e-06), \
            f"Battery charge ({charge}) less than min soc ({self.min_allowed_soc_ratio})"
        assert limit_float_precision(self.used_storage) <= self.capacity or \
            isclose(self.used_storage, self.capacity, rel_tol=1e-06), \
            f"Battery used_storage ({self.used_storage}) surpassed the capacity ({self.capacity})"

        assert 0 <= limit_float_precision(self.offered_sell_kWh[time_slot]) <= max_value
        assert 0 <= limit_float_precision(self.pledged_sell_kWh[time_slot]) <= max_value
        assert 0 <= limit_float_precision(self.pledged_buy_kWh[time_slot]) <= max_value
        assert 0 <= limit_float_precision(self.offered_buy_kWh[time_slot]) <= max_value

    def _calculate_and_update_soc(self, time_slot: DateTime) -> None:
        """Calculate the soc of the storage and update the soc history."""
        self.charge_history[time_slot] = 100.0 * self.used_storage / self.capacity
        self.charge_history_kWh[time_slot] = self.used_storage

    def add_default_values_to_state_profiles(self, future_time_slots: List):
        """Add default values to the state profiles if time_slot key doesn't exist."""
        for time_slot in future_time_slots:
            write_default_to_dict(self.pledged_sell_kWh, time_slot, 0)
            write_default_to_dict(self.pledged_buy_kWh, time_slot, 0)
            write_default_to_dict(self.offered_sell_kWh, time_slot, 0)
            write_default_to_dict(self.offered_buy_kWh, time_slot, 0)

            write_default_to_dict(self.charge_history, time_slot, self.initial_soc)
            write_default_to_dict(self.charge_history_kWh, time_slot, self.initial_capacity_kWh)

            write_default_to_dict(self.energy_to_buy_dict, time_slot, 0)
            write_default_to_dict(self.energy_to_sell_dict, time_slot, 0)
            write_default_to_dict(self.offered_history, time_slot, "-")
            write_default_to_dict(self.used_history, time_slot, "-")

            write_default_to_dict(self.time_series_ess_share, time_slot,
                                  {ESSEnergyOrigin.UNKNOWN: 0.,
                                   ESSEnergyOrigin.LOCAL: 0.,
                                   ESSEnergyOrigin.EXTERNAL: 0.})

    def market_cycle(self, past_time_slot, current_time_slot: DateTime,
                     all_future_time_slots: List[DateTime]):
        """
        Simulate actual Energy flow by removing pledged storage and adding bought energy to the
        used_storage
        """
        self._current_market_slot = current_time_slot
        if GlobalConfig.FUTURE_MARKET_DURATION_HOURS:
            # In case the future market is enabled, the future orders have to be deleted once
            # the market becomes a spot market
            self.offered_buy_kWh[current_time_slot] = 0
            self.offered_sell_kWh[current_time_slot] = 0
        self.add_default_values_to_state_profiles(all_future_time_slots)

        if past_time_slot:
            self._used_storage -= self.pledged_sell_kWh[past_time_slot]
            self._used_storage += self.pledged_buy_kWh[past_time_slot]

        self._clamp_energy_to_sell_kWh([current_time_slot, *all_future_time_slots])
        self._clamp_energy_to_buy_kWh([current_time_slot, *all_future_time_slots])
        self._calculate_and_update_soc(current_time_slot)

        self.offered_history[current_time_slot] = self.offered_sell_kWh[current_time_slot]

        if past_time_slot:
            for energy_type in self._used_storage_share:
                self.time_series_ess_share[past_time_slot][energy_type.origin] += energy_type.value

    def delete_past_state_values(self, current_time_slot: DateTime):
        """
        Clean up values from past market slots that are not used anymore. Useful for
        deallocating memory that is not used anymore.
        """
        to_delete = []
        for market_slot in self.pledged_sell_kWh:
            if is_time_slot_in_past_markets(market_slot, current_time_slot):
                to_delete.append(market_slot)
        for market_slot in to_delete:
            self.pledged_sell_kWh.pop(market_slot, None)
            self.offered_sell_kWh.pop(market_slot, None)
            self.pledged_buy_kWh.pop(market_slot, None)
            self.offered_buy_kWh.pop(market_slot, None)
            self.charge_history.pop(market_slot, None)
            self.charge_history_kWh.pop(market_slot, None)
            self.offered_history.pop(market_slot, None)
            self.used_history.pop(market_slot, None)
            self.energy_to_buy_dict.pop(market_slot, None)
            self.energy_to_sell_dict.pop(market_slot, None)

    def register_energy_from_posted_bid(self, energy: float, time_slot: DateTime):
        """Register the energy from a posted bid on the market."""
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.offered_buy_kWh[time_slot] += energy
        self._clamp_energy_to_buy_kWh([time_slot])

    def register_energy_from_posted_offer(self, energy: float, time_slot: DateTime):
        """Register the energy from a posted offer on the market."""
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.offered_sell_kWh[time_slot] += energy
        self._clamp_energy_to_sell_kWh([time_slot])

    def reset_offered_sell_energy(self, energy: float, time_slot: DateTime):
        """Reset the offered sell energy amount."""
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.offered_sell_kWh[time_slot] = energy
        self._clamp_energy_to_sell_kWh([time_slot])

    def reset_offered_buy_energy(self, energy: float, time_slot: DateTime):
        """Reset the offered buy energy amount."""
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.offered_buy_kWh[time_slot] = energy
        self._clamp_energy_to_buy_kWh([time_slot])

    def remove_energy_from_deleted_offer(self, energy: float, time_slot: DateTime):
        """
        Unregister the energy from a deleted offer, in order to be available for following offers.
        """
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.offered_sell_kWh[time_slot] -= energy
        self._clamp_energy_to_sell_kWh([time_slot])

    def register_energy_from_one_sided_market_accept_offer(
            self, energy: float, time_slot: DateTime,
            energy_origin: ESSEnergyOrigin = ESSEnergyOrigin.UNKNOWN):
        """
        Register energy from one sided market accept offer operation. Similar behavior as
        register_energy_from_bid_trade with the exception that offered_buy_kWh is not used in
        one-sided markets (because there is no concept of bid, the storage never actually offers
        energy, the buyers with access to the market can accept it).
        """
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.pledged_buy_kWh[time_slot] += energy
        self._track_energy_bought_type(energy, energy_origin)
        self._clamp_energy_to_buy_kWh([time_slot])

    def register_energy_from_bid_trade(
            self, energy: float, time_slot: DateTime,
            energy_origin: ESSEnergyOrigin = ESSEnergyOrigin.UNKNOWN):
        """Register energy from a bid trade event."""
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.pledged_buy_kWh[time_slot] += energy
        self.offered_buy_kWh[time_slot] -= energy
        self._track_energy_bought_type(energy, energy_origin)
        self._clamp_energy_to_buy_kWh([time_slot])

    def register_energy_from_offer_trade(self, energy: float, time_slot: DateTime):
        """Register energy from an offer trade event."""
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.pledged_sell_kWh[time_slot] += energy
        self.offered_sell_kWh[time_slot] -= energy
        self._track_energy_sell_type(energy)
        self._clamp_energy_to_sell_kWh([time_slot])

    def _track_energy_bought_type(self, energy: float, energy_origin: ESSEnergyOrigin):
        self._used_storage_share.append(EnergyOrigin(energy_origin, energy))

    # ESS Energy being utilized based on FIRST-IN FIRST-OUT mechanism
    def _track_energy_sell_type(self, energy: float):
        while limit_float_precision(energy) > 0 and len(self._used_storage_share) > 0:
            first_in_energy_with_origin = self._used_storage_share[0]
            if energy >= first_in_energy_with_origin.value:
                energy -= first_in_energy_with_origin.value
                self._used_storage_share.pop(0)
            elif energy < first_in_energy_with_origin.value:
                residual = first_in_energy_with_origin.value - energy
                self._used_storage_share[0] = EnergyOrigin(
                    first_in_energy_with_origin.origin, residual)
                energy = 0

    def get_available_energy_to_buy_kWh(self, time_slot: DateTime) -> float:
        """Retrieve the amount of energy that the storage can buy in the given time slot."""
        if self.free_storage(time_slot) == 0:
            return 0.0

        self._clamp_energy_to_buy_kWh([time_slot])
        energy_kWh = self.energy_to_buy_dict[time_slot]
        if self._has_battery_reached_max_charge_power(abs(energy_kWh), time_slot):
            return 0.0
        assert energy_kWh > -FLOATING_POINT_TOLERANCE
        return energy_kWh

    def get_available_energy_to_sell_kWh(self, time_slot: DateTime) -> float:
        """Retrieve the amount of energy that the storage can sell in the given time slot."""
        if self.used_storage == 0:
            return 0.0
        energy_sell_dict = self._clamp_energy_to_sell_kWh([time_slot])
        energy_kWh = energy_sell_dict[time_slot]
        if self._has_battery_reached_max_discharge_power(energy_kWh, time_slot):
            return 0.0
        assert energy_kWh >= -FLOATING_POINT_TOLERANCE
        return energy_kWh

    def get_soc_level(self, time_slot: DateTime) -> float:
        """Get the SOC level of the storage, in percentage units."""
        if self.charge_history[time_slot] == "-":
            return self.used_storage / self.capacity
        return self.charge_history[time_slot] / 100.0

    def to_dict(self, time_slot: DateTime) -> Dict:
        """Get a dict with the current stats of the storage according to timeslot."""
        return {
            "energy_to_sell": self.energy_to_sell_dict[time_slot],
            "energy_active_in_bids": self.offered_sell_kWh[time_slot],
            "energy_to_buy": self.energy_to_buy_dict[time_slot],
            "energy_active_in_offers": self.offered_buy_kWh[time_slot],
            "free_storage": self.free_storage(time_slot),
            "used_storage": self.used_storage,
        }


class UnexpectedStateException(Exception):
    """Exception raised when the state of a device is unexpected."""
