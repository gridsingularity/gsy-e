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
from collections import defaultdict
from typing import Optional, TYPE_CHECKING, DefaultDict

import pendulum
from gsy_framework.constants_limits import GlobalConfig, FLOATING_POINT_TOLERANCE
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.forward_markets.forward_profile import ForwardTradeProfileGenerator
from gsy_framework.utils import convert_kW_to_kWh

from gsy_e.constants import FORWARD_MARKET_MAX_DURATION_YEARS
from gsy_e.models.strategy.state import LoadState, PVState

if TYPE_CHECKING:
    from gsy_e.models.strategy.state import StateInterface
    from gsy_e.models.area import AreaBase


class _BaseMarketEnergyParams(ABC):
    """
    Base class for the energy parameters of specific markets.
    The children of these classes should not be instantiated by classes other than the
    ForwardEnergyParams child classes.
    """

    def __init__(self, posted_energy_kWh: DefaultDict):
        self._posted_energy_kWh = posted_energy_kWh
        self._area: Optional["AreaBase"] = None
        self._profile_generator: Optional["ForwardTradeProfileGenerator"] = None

    def activate(self, area: "AreaBase", profile_generator: "ForwardTradeProfileGenerator"):
        """
        Activate the energy parameters by providing extra arguments that are generated during the
        activation process.
        """
        self._area = area
        self._profile_generator = profile_generator

    @abstractmethod
    def get_posted_energy_kWh(self, market_slot: pendulum.DateTime) -> float:
        """Get the already posted energy from the asset for this market slot."""

    @abstractmethod
    def increment_posted_energy(self, market_slot: pendulum.DateTime, posted_energy_kWh: float):
        """Increment the posted energy of the asset."""

    @abstractmethod
    def decrement_posted_energy(self, market_slot: pendulum.DateTime, posted_energy_kWh: float):
        """Decrement the posted energy of the asset."""

    @abstractmethod
    def get_available_load_energy_kWh(
        self, market_slot: pendulum.DateTime, state: "LoadState", peak_energy_kWh: float
    ) -> float:
        """Get the available (not traded) energy of a load asset."""

    @abstractmethod
    def get_available_pv_energy_kWh(
        self, market_slot: pendulum.DateTime, state: "PVState", peak_energy_kWh: float
    ) -> float:
        """Get the available (not traded) energy of a PV asset."""

    @abstractmethod
    def event_load_traded_energy(
        self, energy_kWh: float, market_slot: pendulum.DateTime, state: "LoadState"
    ):
        """Trigger actions on a trade event of a load asset."""

    @abstractmethod
    def event_pv_traded_energy(
        self, energy_kWh: float, market_slot: pendulum.DateTime, state: "PVState"
    ):
        """Trigger actions on a trade event of a PV asset."""


class _IntradayEnergyParams(_BaseMarketEnergyParams):
    """
    Energy parameters for the intraday market.
    Should only be instantiated by the ForwardEnergyParams and its child classes.
    """

    def get_posted_energy_kWh(self, market_slot: pendulum.DateTime) -> float:
        return self._posted_energy_kWh[market_slot]

    def increment_posted_energy(self, market_slot: pendulum.DateTime, posted_energy_kWh: float):
        self._posted_energy_kWh[market_slot] += posted_energy_kWh

    def decrement_posted_energy(self, market_slot: pendulum.DateTime, posted_energy_kWh: float):
        self._posted_energy_kWh[market_slot] -= posted_energy_kWh

    def get_available_load_energy_kWh(
        self, market_slot: pendulum.DateTime, state: "LoadState", peak_energy_kWh: float
    ) -> float:
        return state.get_energy_requirement_Wh(market_slot) / 1000.0

    def get_available_pv_energy_kWh(
        self, market_slot: pendulum.DateTime, state: "PVState", peak_energy_kWh: float
    ) -> float:
        return state.get_available_energy_kWh(market_slot)

    def event_load_traded_energy(
        self, energy_kWh: float, market_slot: pendulum.DateTime, state: "LoadState"
    ):
        state.decrement_energy_requirement(
            purchased_energy_Wh=energy_kWh * 1000, time_slot=market_slot, area_name=self._area.name
        )

    def event_pv_traded_energy(
        self, energy_kWh: float, market_slot: pendulum.DateTime, state: "PVState"
    ):
        state.decrement_available_energy(
            sold_energy_kWh=energy_kWh, time_slot=market_slot, area_name=self._area.name
        )


class _DayForwardEnergyParams(_BaseMarketEnergyParams):
    """
    Energy parameters for the day forward market.
    Should only be instantiated by the ForwardEnergyParams and its child classes.
    """

    @staticmethod
    def _day_forward_slots(market_slot: pendulum.DateTime):
        """Get the market slots for the day forward market."""
        return [
            market_slot,
            market_slot + pendulum.duration(minutes=15),
            market_slot + pendulum.duration(minutes=30),
            market_slot + pendulum.duration(minutes=45),
        ]

    def get_posted_energy_kWh(self, market_slot: pendulum.DateTime) -> float:
        return max(self._posted_energy_kWh[slot] for slot in self._day_forward_slots(market_slot))

    def increment_posted_energy(self, market_slot: pendulum.DateTime, posted_energy_kWh: float):
        slots = self._day_forward_slots(market_slot)
        for slot in slots:
            self._posted_energy_kWh[slot] += posted_energy_kWh

    def decrement_posted_energy(self, market_slot: pendulum.DateTime, posted_energy_kWh: float):
        for slot in self._day_forward_slots(market_slot):
            self._posted_energy_kWh[slot] -= posted_energy_kWh

    def get_available_load_energy_kWh(
        self, market_slot: pendulum.DateTime, state: "LoadState", peak_energy_kWh: float
    ) -> float:
        return min(
            state.get_energy_requirement_Wh(slot) / 1000.0
            for slot in self._day_forward_slots(market_slot)
        )

    def get_available_pv_energy_kWh(
        self, market_slot: pendulum.DateTime, state: "PVState", peak_energy_kWh: float
    ) -> float:
        return min(
            state.get_energy_production_forecast_kWh(slot)
            for slot in self._day_forward_slots(market_slot)
        )

    def event_load_traded_energy(
        self, energy_kWh: float, market_slot: pendulum.DateTime, state: "LoadState"
    ):
        for slot in self._day_forward_slots(market_slot):
            state.decrement_energy_requirement(
                purchased_energy_Wh=energy_kWh * 1000, time_slot=slot, area_name=self._area.name
            )

    def event_pv_traded_energy(
        self, energy_kWh: float, market_slot: pendulum.DateTime, state: "PVState"
    ):
        for slot in self._day_forward_slots(market_slot):
            state.decrement_available_energy(
                sold_energy_kWh=energy_kWh, time_slot=slot, area_name=self._area.name
            )


class _LongForwardEnergyParameters(_BaseMarketEnergyParams):
    """
    Energy parameters for the week / month / year forward markets.
    Should only be instantiated by the ForwardEnergyParams and its child classes.
    """

    def __init__(self, posted_energy_kWh: DefaultDict, product_type: AvailableMarketTypes):
        super().__init__(posted_energy_kWh)
        self._product_type = product_type

    def get_posted_energy_kWh(self, market_slot: pendulum.DateTime) -> float:
        return 0.0

    def increment_posted_energy(self, market_slot: pendulum.DateTime, posted_energy_kWh: float):
        return

    def decrement_posted_energy(self, market_slot: pendulum.DateTime, posted_energy_kWh: float):
        return

    def get_available_load_energy_kWh(
        self, market_slot: pendulum.DateTime, state: "LoadState", peak_energy_kWh: float
    ) -> float:

        # This is the part where the week / month / year forward markets' available energy is
        # calculated. In order for the available energy for a bid to be calculated, the available
        # peak energy for the market slot duration needs to be calculated (essentially the peak
        # energy that has not been yet traded). One time slot should be used as reference that is
        # known in advance to have non-zero values (in our case 12:00), and by calculating the
        # scaling factor (ratio of available - not-traded energy by the total energy that can be
        # traded by this asset on this market slot) the available peak energy can be calculated by
        # multiplying the scaling factor by the already known peak energy of the asset.
        reference_slot = market_slot.set(hour=12, minute=0)

        if state.get_desired_energy_Wh(reference_slot) <= FLOATING_POINT_TOLERANCE:
            scaling_factor = 0.0
        else:
            scaling_factor = state.get_energy_requirement_Wh(
                reference_slot
            ) / state.get_desired_energy_Wh(reference_slot)
        return abs(scaling_factor) * peak_energy_kWh

    def get_available_pv_energy_kWh(
        self, market_slot: pendulum.DateTime, state: "PVState", peak_energy_kWh: float
    ) -> float:

        # This is the part where the week / month / year forward markets' available energy is
        # calculated. In order for the available energy for a bid to be calculated, the available
        # peak energy for the market slot duration needs to be calculated (essentially the peak
        # energy that has not been yet traded). One time slot should be used as reference that is
        # known in advance to have non-zero values (in our case 12:00), and by calculating the
        # scaling factor (ratio of available - not-traded energy by the total energy that can be
        # traded by this asset on this market slot) the available peak energy can be calculated by
        # multiplying the scaling factor by the already known peak energy of the asset.
        reference_slot = market_slot.set(hour=12, minute=0)

        if state.get_energy_production_forecast_kWh(reference_slot) <= FLOATING_POINT_TOLERANCE:
            scaling_factor = 0.0
        else:
            scaling_factor = state.get_available_energy_kWh(
                reference_slot
            ) / state.get_energy_production_forecast_kWh(reference_slot)
        return abs(scaling_factor) * peak_energy_kWh

    def event_load_traded_energy(
        self, energy_kWh: float, market_slot: pendulum.DateTime, state: "LoadState"
    ):
        trade_profile = self._profile_generator.generate_trade_profile(
            energy_kWh=energy_kWh, market_slot=market_slot, product_type=self._product_type
        )

        for time_slot, energy_value_kWh in trade_profile.items():
            state.decrement_energy_requirement(
                purchased_energy_Wh=energy_value_kWh * 1000,
                time_slot=time_slot,
                area_name=self._area.name,
            )

    def event_pv_traded_energy(
        self, energy_kWh: float, market_slot: pendulum.DateTime, state: "PVState"
    ):
        # Create a new profile that spreads the trade energy across multiple slots. The values
        # of this new profile are obtained by scaling the values of the standard solar profile
        trade_profile = self._profile_generator.generate_trade_profile(
            energy_kWh=energy_kWh, market_slot=market_slot, product_type=self._product_type
        )

        for time_slot, energy_value_kWh in trade_profile.items():
            state.decrement_available_energy(
                sold_energy_kWh=energy_value_kWh, time_slot=time_slot, area_name=self._area.name
            )


class ForwardEnergyParams(ABC):
    """Common abstract base class for the energy parameters of the forward strategies."""

    def __init__(self):
        self._posted_energy_kWh: DefaultDict = defaultdict(lambda: 0.0)
        self._forward_energy_params = {
            AvailableMarketTypes.INTRADAY: _IntradayEnergyParams(self._posted_energy_kWh),
            AvailableMarketTypes.DAY_FORWARD: _DayForwardEnergyParams(self._posted_energy_kWh),
            AvailableMarketTypes.WEEK_FORWARD: _LongForwardEnergyParameters(
                self._posted_energy_kWh, AvailableMarketTypes.WEEK_FORWARD
            ),
            AvailableMarketTypes.MONTH_FORWARD: _LongForwardEnergyParameters(
                self._posted_energy_kWh, AvailableMarketTypes.MONTH_FORWARD
            ),
            AvailableMarketTypes.YEAR_FORWARD: _LongForwardEnergyParameters(
                self._posted_energy_kWh, AvailableMarketTypes.YEAR_FORWARD
            ),
        }

        self._area = None
        self._profile_generator: Optional[ForwardTradeProfileGenerator] = None

    def get_posted_energy_kWh(
        self, market_slot: pendulum.DateTime, product_type: AvailableMarketTypes
    ) -> float:
        """Retrieve the already posted energy on this market slot."""
        return self._forward_energy_params[product_type].get_posted_energy_kWh(market_slot)

    def increment_posted_energy(
        self,
        market_slot: pendulum.DateTime,
        posted_energy_kWh: float,
        market_type: AvailableMarketTypes,
    ):
        """
        Increase the posted energy of the strategy. Needs to handle only intraday and day ahead
        since these are the only 2 market types that can operate at the same market slots
        concurrently.
        """
        self._forward_energy_params[market_type].increment_posted_energy(
            market_slot, posted_energy_kWh
        )

    def decrement_posted_energy(
        self,
        market_slot: pendulum.DateTime,
        posted_energy_kWh: float,
        market_type: AvailableMarketTypes,
    ):
        """
        Decrease the posted energy of the strategy. Needs to handle only intraday and day ahead
        since these are the only 2 market types that can operate at the same market slots
        concurrently.
        """
        self._forward_energy_params[market_type].decrement_posted_energy(
            market_slot, posted_energy_kWh
        )

    @abstractmethod
    def serialize(self):
        """Return dict with the current energy parameter values."""

    @abstractmethod
    def get_available_energy_kWh(
        self, market_slot: pendulum.DateTime, market_type: AvailableMarketTypes
    ):
        """Get the available offer energy of the PV."""

    def event_activate_energy(self, area):
        """Initialize values that are required to compute the energy values of the asset."""
        for params in self._forward_energy_params.values():
            params.activate(area, self._profile_generator)

    @abstractmethod
    def event_traded_energy(
        self, energy_kWh: float, market_slot: pendulum.DateTime, product_type: AvailableMarketTypes
    ):
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


class ConsumptionStandardProfileEnergyParameters(ForwardEnergyParams):
    """Energy parameters of the load strategy for the forward markets."""

    def __init__(self, capacity_kW):
        super().__init__()
        self.capacity_kW: float = capacity_kW
        self._state = LoadState()

    @property
    def state(self) -> LoadState:
        """Retrieve the internal state of the asset."""
        return self._state

    def serialize(self):
        """Return dict with the current energy parameter values."""
        return {"capacity_kW": self.capacity_kW}

    @property
    def peak_energy_kWh(self):
        """Peak energy of the load profile in kWh."""
        return convert_kW_to_kWh(self.capacity_kW, self._area.config.slot_length)

    def get_available_energy_kWh(
        self, market_slot: pendulum.DateTime, market_type: AvailableMarketTypes
    ) -> float:
        """
        Get the available energy of the Load for one market slot. The available energy is the
        energy that the Load can consumed, but has not been traded yet.
        """
        return self._forward_energy_params[market_type].get_available_load_energy_kWh(
            market_slot, self.state, self.peak_energy_kWh
        )

    def event_activate_energy(self, area):
        """Initialize values that are required to compute the energy values of the asset."""
        self._area = area
        self._profile_generator = ForwardTradeProfileGenerator(peak_kWh=self.peak_energy_kWh)

        for i in range(FORWARD_MARKET_MAX_DURATION_YEARS + 1):
            capacity_profile = self._profile_generator.generate_trade_profile(
                energy_kWh=self.peak_energy_kWh,
                market_slot=GlobalConfig.start_date.start_of("year").add(years=i),
                product_type=AvailableMarketTypes.YEAR_FORWARD,
            )
            for time_slot, energy_kWh in capacity_profile.items():
                self.state.set_desired_energy(energy_kWh * 1000, time_slot)

        super().event_activate_energy(area)

    def event_traded_energy(
        self, energy_kWh: float, market_slot: pendulum.DateTime, product_type: AvailableMarketTypes
    ):
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
        self._forward_energy_params[product_type].event_load_traded_energy(
            energy_kWh, market_slot, self.state
        )


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
        return {"capacity_kW": self.capacity_kW}

    @property
    def peak_energy_kWh(self):
        """Energy peak of the PV profile in kWh."""
        return convert_kW_to_kWh(self.capacity_kW, self._area.config.slot_length)

    def get_available_energy_kWh(
        self, market_slot: pendulum.DateTime, market_type: AvailableMarketTypes
    ) -> float:
        """
        Get the available energy of the PV for one market slot. The available energy is the energy
        that the PV can produce, but has not been traded yet.
        """
        return self._forward_energy_params[market_type].get_available_pv_energy_kWh(
            market_slot, self.state, self.peak_energy_kWh
        )

    def event_activate_energy(self, area):
        """Initialize values that are required to compute the energy values of the asset."""
        self._area = area
        self._profile_generator = ForwardTradeProfileGenerator(peak_kWh=self.peak_energy_kWh)

        for i in range(FORWARD_MARKET_MAX_DURATION_YEARS + 1):
            capacity_profile = self._profile_generator.generate_trade_profile(
                energy_kWh=self.peak_energy_kWh,
                market_slot=GlobalConfig.start_date.start_of("year").add(years=i),
                product_type=AvailableMarketTypes.YEAR_FORWARD,
            )
            for time_slot, energy_kWh in capacity_profile.items():
                self.state.set_available_energy(energy_kWh, time_slot)

        super().event_activate_energy(area)

    def event_traded_energy(
        self, energy_kWh: float, market_slot: pendulum.DateTime, product_type: AvailableMarketTypes
    ):
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
        self._forward_energy_params[product_type].event_pv_traded_energy(
            energy_kWh, market_slot, self.state
        )
