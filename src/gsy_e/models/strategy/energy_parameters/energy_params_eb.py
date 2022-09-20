# Copyright 2018 Grid Singularity
# This file is part of Grid Singularity Exchange
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.

# You should have received a copy of the GNU General Public License along with this program. If
# not, see <http://www.gnu.org/licenses/>.

"""
This module contains classes to define the energy parameters (planning algorithms) of the
strategies for the Electric Blue exchange. These classes trade on forward markets that span over
multiple 15 minutes slots. Therefore, they need to spread the single energy values (obtained from
received orders) into multiple timeslots. This happens following the line of a Standard Solar
Profile.

NOTE: The intraday product should not use this approach, since it already trades on single
15-minutes timeslots.
"""
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING, Dict

import pendulum
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.forward_markets.forward_profile import ForwardTradeProfileGenerator
from gsy_framework.utils import convert_kW_to_kWh

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.state import LoadState, PVState

if TYPE_CHECKING:
    from gsy_e.models.state import StateInterface


class ForwardEnergyParams(ABC):
    """Common abstract base class for the energy parameters of the forward strategies."""
    def __init__(self):
        self._posted_energy_kWh: Dict = {}

    def get_posted_energy_kWh(
            self, market_slot: pendulum.DateTime, market_type: AvailableMarketTypes) -> float:
        """Retrieve the already posted energy on this market slot."""
        if market_type == AvailableMarketTypes.INTRADAY:
            if market_slot not in self._posted_energy_kWh:
                self._posted_energy_kWh[market_slot] = 0.

            return self._posted_energy_kWh[market_slot]
        if market_type == AvailableMarketTypes.DAY_FORWARD:
            for slot in self.day_forward_slots(market_slot):
                if slot not in self._posted_energy_kWh:
                    self._posted_energy_kWh[slot] = 0.
            return max(
                self._posted_energy_kWh[slot]
                for slot in self.day_forward_slots(market_slot)
            )
        return 0.

    def increment_posted_energy(
            self, market_slot: pendulum.DateTime, posted_energy_kWh: float,
            market_type: AvailableMarketTypes):
        """
        Increase the posted energy of the strategy. Needs to handle only intraday and day ahead
        since these are the only 2 market types that can operate at the same market slots
        concurrently.
        """
        if market_type not in [AvailableMarketTypes.INTRADAY, AvailableMarketTypes.DAY_FORWARD]:
            return
        if market_type == AvailableMarketTypes.INTRADAY:
            if market_slot not in self._posted_energy_kWh:
                self._posted_energy_kWh[market_slot] = 0.
            self._posted_energy_kWh[market_slot] += posted_energy_kWh
        if market_type == AvailableMarketTypes.DAY_FORWARD:
            slots = self.day_forward_slots(market_slot)
            for slot in slots:
                if slot not in self._posted_energy_kWh:
                    self._posted_energy_kWh[slot] = 0.
                self._posted_energy_kWh[slot] += posted_energy_kWh

    def decrement_posted_energy(
            self, market_slot: pendulum.DateTime, posted_energy_kWh: float,
            market_type: AvailableMarketTypes):
        """
        Decrease the posted energy of the strategy. Needs to handle only intraday and day ahead
        since these are the only 2 market types that can operate at the same market slots
        concurrently.
        """
        if market_type not in [AvailableMarketTypes.INTRADAY, AvailableMarketTypes.DAY_FORWARD]:
            return

        assert market_slot in self._posted_energy_kWh, \
            "Failed to decrement posted energy, the posted energy should be updated on every " \
            "bid or offer before decrementing it."

        if market_type == AvailableMarketTypes.INTRADAY:
            self._posted_energy_kWh[market_slot] -= posted_energy_kWh
        if market_type == AvailableMarketTypes.DAY_FORWARD:
            slots = self.day_forward_slots(market_slot)
            for slot in slots:
                self._posted_energy_kWh[slot] -= posted_energy_kWh

    @abstractmethod
    def serialize(self):
        """Return dict with the current energy parameter values."""

    @abstractmethod
    def get_available_energy_kWh(
            self, market_slot: pendulum.DateTime, market_type: AvailableMarketTypes):
        """Get the available offer energy of the PV."""

    @abstractmethod
    def event_activate_energy(self, area):
        """Initialize values that are required to compute the energy values of the asset."""

    @abstractmethod
    def event_traded_energy(
            self, energy_kWh: float, market_slot: pendulum.DateTime,
            product_type: AvailableMarketTypes):
        """
        When a trade happens, we want to split the energy through the entire year following a
        standard solar profile.

        Args:
            energy_kWh: the traded energy in kWh.
            market_slot: the slot targeted by the trade. For forward exchanges, this represents
                the entire period of time over which the trade profile will be generated.
            product_type: One of the available market types.
        """

    @property
    @abstractmethod
    def state(self) -> "StateInterface":
        """Retrieve the internal state of the asset."""

    @staticmethod
    def day_forward_slots(market_slot: pendulum.DateTime):
        """Get the market slots for the day forward market."""
        return [
            market_slot,
            market_slot + pendulum.duration(minutes=15),
            market_slot + pendulum.duration(minutes=30),
            market_slot + pendulum.duration(minutes=45)]


class ConsumptionStandardProfileEnergyParameters(ForwardEnergyParams):
    """Energy parameters of the load strategy for the forward markets."""

    def __init__(self, capacity_kW):
        super().__init__()
        self.capacity_kW: float = capacity_kW

        self._state = LoadState()
        self._area = None
        self._profile_generator: Optional[ForwardTradeProfileGenerator] = None

    @property
    def state(self) -> LoadState:
        """Retrieve the internal state of the asset."""
        return self._state

    def serialize(self):
        """Return dict with the current energy parameter values."""
        return {
            "capacity_kW": self.capacity_kW
        }

    @property
    def capacity_kWh(self):
        """Capacity of the load in kWh."""
        return convert_kW_to_kWh(self.capacity_kW, self._area.config.slot_length)

    def get_available_energy_kWh(
            self, market_slot: pendulum.DateTime, market_type: AvailableMarketTypes):
        """Get the available bid energy of the load."""
        if market_type == AvailableMarketTypes.INTRADAY:
            return self._state.get_energy_requirement_Wh(market_slot) / 1000.0
        if market_type == AvailableMarketTypes.DAY_FORWARD:
            return min(
                self._state.get_energy_requirement_Wh(slot) / 1000.0
                for slot in self.day_forward_slots(market_slot)
            )

        reference_slot = market_slot.set(hour=12, minute=0, tz=pendulum.UTC)

        if self._state.get_desired_energy_Wh(reference_slot) <= FLOATING_POINT_TOLERANCE:
            scaling_factor = 0.
        else:
            scaling_factor = (
                    self._state.get_energy_requirement_Wh(reference_slot) /
                    self._state.get_desired_energy_Wh(reference_slot))
        return abs(scaling_factor) * self.capacity_kWh

    def event_activate_energy(self, area):
        """Initialize values that are required to compute the energy values of the asset."""
        self._area = area
        self._profile_generator = ForwardTradeProfileGenerator(
            peak_kWh=self.capacity_kWh)
        for i in range(4):
            capacity_profile = self._profile_generator.generate_trade_profile(
                energy_kWh=self.capacity_kWh,
                market_slot=pendulum.now(tz=pendulum.UTC).start_of("year").add(years=i),
                product_type=AvailableMarketTypes.YEAR_FORWARD)
            for time_slot, energy_kWh in capacity_profile.items():
                self._state.set_desired_energy(energy_kWh * 1000, time_slot)

    def event_traded_energy(
            self, energy_kWh: float, market_slot: pendulum.DateTime,
            product_type: AvailableMarketTypes):
        """
        When a trade happens, we want to split the energy through the entire year following a
        standard solar profile.

        Args:
            energy_kWh: the traded energy in kWh.
            market_slot: the slot targeted by the trade. For forward exchanges, this represents
                the entire period of time over which the trade profile will be generated.
            product_type: One of the available market types.
        """
        assert self._profile_generator is not None
        if product_type == AvailableMarketTypes.INTRADAY:
            self._state.decrement_energy_requirement(
                purchased_energy_Wh=energy_kWh * 1000,
                time_slot=market_slot.set(tz=pendulum.UTC),
                area_name=self._area.name)
            return
        if product_type == AvailableMarketTypes.DAY_FORWARD:
            for slot in self.day_forward_slots(market_slot):
                self._state.decrement_energy_requirement(
                    purchased_energy_Wh=energy_kWh * 1000,
                    time_slot=slot,
                    area_name=self._area.name)
            return
        # Create a new profile that spreads the trade energy across multiple slots. The values
        # of this new profile are obtained by scaling the values of the standard solar profile
        trade_profile = self._profile_generator.generate_trade_profile(
            energy_kWh=energy_kWh,
            market_slot=market_slot,
            product_type=product_type)

        for time_slot, energy_value_kWh in trade_profile.items():
            self._state.decrement_energy_requirement(
                purchased_energy_Wh=energy_value_kWh * 1000,
                time_slot=time_slot.set(tz=pendulum.UTC),
                area_name=self._area.name)


class ProductionStandardProfileEnergyParameters(ForwardEnergyParams):
    """Energy parameters of the PV strategy for the forward markets."""

    def __init__(self, capacity_kW):
        super().__init__()
        self.capacity_kW: float = capacity_kW

        self._state = PVState()
        self._area = None
        self._profile_generator: Optional[ForwardTradeProfileGenerator] = None

    @property
    def state(self) -> PVState:
        """Retrieve the internal state of the asset."""
        return self._state

    def serialize(self):
        """Return dict with the current energy parameter values."""
        return {
            "capacity_kW": self.capacity_kW
        }

    @property
    def capacity_kWh(self):
        """Capacity of the PV in kWh."""
        return convert_kW_to_kWh(self.capacity_kW, self._area.config.slot_length)

    def get_available_energy_kWh(
            self, market_slot: pendulum.DateTime, market_type: AvailableMarketTypes):
        """Get the available offer energy of the PV."""
        if market_type == AvailableMarketTypes.INTRADAY:
            self._state.get_available_energy_kWh(market_slot)
        elif market_type == AvailableMarketTypes.DAY_FORWARD:
            return min(
                self._state.get_energy_production_forecast_kWh(slot)
                for slot in self.day_forward_slots(market_slot)
            )

        reference_slot = market_slot.set(hour=12, minute=0)

        if self._state.get_energy_production_forecast_kWh(
                reference_slot) <= FLOATING_POINT_TOLERANCE:
            scaling_factor = 0.
        else:
            scaling_factor = (
                    self._state.get_available_energy_kWh(reference_slot) /
                    self._state.get_energy_production_forecast_kWh(reference_slot))
        return abs(scaling_factor) * self.capacity_kWh

    def event_activate_energy(self, area):
        """Initialize values that are required to compute the energy values of the asset."""
        self._area = area
        self._profile_generator = ForwardTradeProfileGenerator(
            peak_kWh=self.capacity_kWh)
        capacity_profile = self._profile_generator.generate_trade_profile(
            energy_kWh=self.capacity_kWh,
            market_slot=pendulum.now().start_of("year"),
            product_type=AvailableMarketTypes.YEAR_FORWARD)
        for time_slot, energy_kWh in capacity_profile.items():
            self._state.set_available_energy(energy_kWh, time_slot)

    def event_traded_energy(
            self, energy_kWh: float, market_slot: pendulum.DateTime,
            product_type: AvailableMarketTypes):
        """
        Spread the traded energy over the market duration following a standard solar profile.

        The period over which the trade is spread is defined by the `product_type`.
        The period is split into energy slots of 15 minutes.

        Args:
            energy_kWh: the traded energy in kWh.
            market_slot: the slot targeted by the trade. For forward exchanges, this represents
                the entire period of time over which the trade profile will be generated.
            product_type: One of the available market types.
        """
        assert self._profile_generator is not None

        if product_type == AvailableMarketTypes.INTRADAY:
            self._state.decrement_available_energy(
                sold_energy_kWh=energy_kWh,
                time_slot=market_slot,
                area_name=self._area.name)
            return
        if product_type == AvailableMarketTypes.DAY_FORWARD:
            for slot in self.day_forward_slots(market_slot):
                self._state.decrement_available_energy(
                    sold_energy_kWh=energy_kWh,
                    time_slot=slot,
                    area_name=self._area.name)
            return

        # Create a new profile that spreads the trade energy across multiple slots. The values
        # of this new profile are obtained by scaling the values of the standard solar profile
        trade_profile = self._profile_generator.generate_trade_profile(
            energy_kWh=energy_kWh,
            market_slot=market_slot,
            product_type=product_type)

        for time_slot, energy_value_kWh in trade_profile.items():
            self._state.decrement_available_energy(
                sold_energy_kWh=energy_value_kWh,
                time_slot=time_slot,
                area_name=self._area.name)
