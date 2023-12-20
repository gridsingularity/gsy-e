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
from math import copysign
from typing import Dict, Optional

from gsy_framework.utils import (
    convert_pendulum_to_str_in_dict, convert_str_to_pendulum_in_dict)
from pendulum import DateTime

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.gsy_e_core.util import is_time_slot_in_past_markets


class UnexpectedStateException(Exception):
    """Exception raised when the state of a device is unexpected."""


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

    @abstractmethod
    def get_results_dict(self, current_time_slot: DateTime) -> dict:
        """Return a dict with the state values that can be used in results."""

    def __str__(self):
        return self.__class__.__name__


class DummyState(StateInterface):
    """Empty state for usage in strategies that do not need state but to enable the
    endpoint_buffer to be access the state methods."""

    def get_state(self) -> Dict:
        """Return the current state of the device."""
        return {}

    def restore_state(self, state_dict: Dict):
        """Update the state of the device using the provided dictionary."""

    def delete_past_state_values(self, current_time_slot: DateTime):
        """Delete the state of the device before the given time slot."""

    def get_results_dict(self, current_time_slot: DateTime) -> dict:
        """Return a dict with the state values that can be used in results."""
        return {}


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
