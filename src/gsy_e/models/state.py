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
from typing import Dict, Optional

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.utils import (
    convert_pendulum_to_str_in_dict, convert_str_to_pendulum_in_dict, convert_kW_to_kWh)
from pendulum import DateTime

from gsy_framework.utils import limit_float_precision
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
        self._unsettled_deviation_kWh[time_slot] = \
            abs(self._forecast_measurement_deviation_kWh[time_slot])

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
        self._desired_energy_Wh = {}
        # Energy that the load needs to consume. It's reduced when new energy is bought
        self._energy_requirement_Wh = {}
        self._total_energy_demanded_Wh = 0

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

    def get_energy_requirement_Wh(self, time_slot, default_value=0.0):
        return self._energy_requirement_Wh.get(time_slot, default_value)

    def set_desired_energy(self, energy, time_slot, overwrite=False):
        if overwrite is False and time_slot in self._energy_requirement_Wh:
            return
        self._energy_requirement_Wh[time_slot] = energy
        self._desired_energy_Wh[time_slot] = energy

    def update_total_demanded_energy(self, time_slot):
        self._total_energy_demanded_Wh += self._desired_energy_Wh.get(time_slot, 0.)

    def can_buy_more_energy(self, time_slot):
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
        for market_slot in self._energy_requirement_Wh.keys():
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
        super().restore_state(state_dict)

        self._available_energy_kWh.update(
            convert_str_to_pendulum_in_dict(state_dict["available_energy_kWh"]))
        self._energy_production_forecast_kWh.update(
            convert_str_to_pendulum_in_dict(state_dict["energy_production_forecast_kWh"]))

    def set_available_energy(self, energy_kWh, time_slot, overwrite=False):
        if overwrite is False and time_slot in self._energy_production_forecast_kWh:
            return
        self._energy_production_forecast_kWh[time_slot] = energy_kWh
        self._available_energy_kWh[time_slot] = energy_kWh

        assert self._energy_production_forecast_kWh[time_slot] >= 0.0

    def get_available_energy_kWh(self, time_slot, default_value=0.0):
        available_energy = self._available_energy_kWh.get(time_slot, default_value)

        assert available_energy >= -FLOATING_POINT_TOLERANCE
        return available_energy

    def decrement_available_energy(self, sold_energy_kWh, time_slot, area_name):
        self._available_energy_kWh[time_slot] -= sold_energy_kWh
        assert self._available_energy_kWh[time_slot] >= -FLOATING_POINT_TOLERANCE, (
            f"Available energy for device {area_name} fell below zero "
            f"({self._available_energy_kWh[time_slot]}).")

    def delete_past_state_values(self, current_time_slot: DateTime):
        """Delete data regarding energy production for past market slots."""
        to_delete = []
        for market_slot in self._available_energy_kWh.keys():
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
    def __init__(self):
        super().__init__()

    @property
    def total_energy_demanded_Wh(self):
        return self._total_energy_demanded_Wh

    def get_desired_energy(self, time_slot):
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

    def __init__(self):
        super().__init__()

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
    LOCAL = 1
    EXTERNAL = 2
    UNKNOWN = 3


EnergyOrigin = namedtuple("EnergyOrigin", ("origin", "value"))


class StorageState(StateInterface):
    def __init__(self,
                 initial_soc=StorageSettings.MIN_ALLOWED_SOC,
                 initial_energy_origin=ESSEnergyOrigin.EXTERNAL,
                 capacity=StorageSettings.CAPACITY,
                 max_abs_battery_power_kW=StorageSettings.MAX_ABS_POWER,
                 loss_per_hour=0.01,
                 loss_function=1,
                 min_allowed_soc=StorageSettings.MIN_ALLOWED_SOC):

        self.initial_soc = initial_soc
        self.initial_capacity_kWh = capacity * initial_soc / 100

        self.min_allowed_soc_ratio = min_allowed_soc / 100

        self.capacity = capacity
        self.loss_per_hour = loss_per_hour
        self.loss_function = loss_function
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

    def update_used_storage_share(self, energy, source=ESSEnergyOrigin.UNKNOWN):
        self._used_storage_share.append(EnergyOrigin(source, energy))

    @property
    def get_used_storage_share(self):
        return self._used_storage_share

    def free_storage(self, time_slot):
        """
        Storage, that has not been promised or occupied
        """
        in_use = self._used_storage \
            - self.pledged_sell_kWh[time_slot] \
            + self.pledged_buy_kWh[time_slot]
        return self.capacity - in_use

    def max_offer_energy_kWh(self, time_slot):
        return self._battery_energy_per_slot - self.pledged_sell_kWh[time_slot] \
               - self.offered_sell_kWh[time_slot]

    def max_buy_energy_kWh(self, time_slot):
        return self._battery_energy_per_slot - self.pledged_buy_kWh[time_slot] \
               - self.offered_buy_kWh[time_slot]

    def set_battery_energy_per_slot(self, slot_length):
        self._battery_energy_per_slot = convert_kW_to_kWh(self.max_abs_battery_power_kW,
                                                          slot_length)

    def has_battery_reached_max_power(self, energy, time_slot):
        return limit_float_precision(abs(energy
                                     + self.pledged_sell_kWh[time_slot]
                                     + self.offered_sell_kWh[time_slot]
                                     - self.pledged_buy_kWh[time_slot]
                                     - self.offered_buy_kWh[time_slot])) > \
               self._battery_energy_per_slot

    def clamp_energy_to_sell_kWh(self, market_slot_time_list):
        """
        Determines available energy to sell for each active market and returns a dict[TIME, FLOAT]
        """
        accumulated_pledged = 0
        accumulated_offered = 0
        for time_slot in market_slot_time_list:
            accumulated_pledged += self.pledged_sell_kWh[time_slot]
            accumulated_offered += self.offered_sell_kWh[time_slot]

        energy = self.used_storage \
            - accumulated_pledged \
            - accumulated_offered \
            - self.min_allowed_soc_ratio * self.capacity
        storage_dict = {}
        for time_slot in market_slot_time_list:
            storage_dict[time_slot] = limit_float_precision(min(
                                                            energy / len(market_slot_time_list),
                                                            self.max_offer_energy_kWh(time_slot),
                                                            self._battery_energy_per_slot))
            self.energy_to_sell_dict[time_slot] = storage_dict[time_slot]

        return storage_dict

    def clamp_energy_to_buy_kWh(self, market_slot_time_list):
        """
        Determines amount of energy that can be bought for each active market and writes it to
        self.energy_to_buy_dict
        """

        accumulated_bought = 0
        accumulated_sought = 0
        for time_slot in market_slot_time_list:
            accumulated_bought += self.pledged_buy_kWh[time_slot]
            accumulated_sought += self.offered_buy_kWh[time_slot]
        energy = limit_float_precision((self.capacity
                                        - self.used_storage
                                        - accumulated_bought
                                        - accumulated_sought) / len(market_slot_time_list))

        for time_slot in market_slot_time_list:
            clamped_energy = limit_float_precision(
                min(energy, self.max_buy_energy_kWh(time_slot), self._battery_energy_per_slot))
            clamped_energy = max(clamped_energy, 0)
            self.energy_to_buy_dict[time_slot] = clamped_energy

    def check_state(self, time_slot):
        """
        Sanity check of the state variables.
        """
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

    def lose(self, loss_function, loss_per_hour):
        if loss_function == 1:
            if self._used_storage * (1.0 - loss_per_hour) >= 0:
                self._used_storage *= 1.0 - loss_per_hour
            else:
                self._used_storage = 0
        else:
            if self._used_storage >= loss_per_hour:
                self._used_storage += - loss_per_hour
            else:
                self._used_storage = 0

    def tick(self, area, time_slot):
        self.check_state(time_slot)
        self.lose(self.loss_function,
                  self.loss_per_hour * area.config.tick_length.in_seconds() / 3600)

    def calculate_soc_for_time_slot(self, time_slot):
        self.charge_history[time_slot] = 100.0 * self.used_storage / self.capacity
        self.charge_history_kWh[time_slot] = self.used_storage

    def add_default_values_to_state_profiles(self, future_time_slots):
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

    def market_cycle(self, past_time_slot, current_time_slot: DateTime, all_future_time_slots):
        """
        Simulate actual Energy flow by removing pledged storage and adding bought energy to the
        used_storage
        """
        self.add_default_values_to_state_profiles(all_future_time_slots)

        if past_time_slot:
            self._used_storage -= self.pledged_sell_kWh[past_time_slot]
            self._used_storage += self.pledged_buy_kWh[past_time_slot]

        self.calculate_soc_for_time_slot(current_time_slot)
        self.offered_history[current_time_slot] = self.offered_sell_kWh[current_time_slot]

        if past_time_slot:
            for energy_type in self._used_storage_share:
                self.time_series_ess_share[past_time_slot][energy_type.origin] += energy_type.value

    def delete_past_state_values(self, current_time_slot: DateTime):
        to_delete = []
        for market_slot in self.pledged_sell_kWh.keys():
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


class UnexpectedStateException(Exception):
    """Exception raised when the state of a device is unexpected."""
