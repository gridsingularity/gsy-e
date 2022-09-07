from typing import Optional

import pendulum
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.utils import convert_kW_to_kWh

from gsy_e.models.state import LoadState, PVState
from gsy_e.models.strategy.energy_parameters.forward_profile import ForwardTradeProfileGenerator


class ConsumptionStandardProfileEnergyParameters:
    """Energy parameters of the load strategy for the forward markets."""

    def __init__(self, capacity_kW):
        self.state = LoadState()
        self.capacity_kW: float = capacity_kW

        self._area = None
        self._profile_generator: Optional[ForwardTradeProfileGenerator] = None

    def serialize(self):
        """Return dict with the current energy parameter values."""
        return {
            "capacity_kW": self.capacity_kW
        }

    def event_activate_energy(self, area):
        """Update energy requirement upon the activation event."""
        self._area = area
        self._profile_generator = ForwardTradeProfileGenerator(
            peak_kWh=convert_kW_to_kWh(self.capacity_kW, self._area.config.slot_length))

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
        # Create a new profile that spreads the trade energy across multiple slots. The values
        # of this new profile are obtained by scaling the values of the standard solar profile
        trade_profile = self._profile_generator.generate_trade_profile(
            energy_kWh=energy_kWh,
            market_slot=market_slot,
            product_type=product_type)

        for time_slot, energy_value_kWh in trade_profile.items():
            self.state.decrement_energy_requirement(
                purchased_energy_Wh=energy_value_kWh * 1000,
                time_slot=time_slot,
                area_name=self._area.name)


class ProductionStandardProfileEnergyParameters:
    """Energy parameters of the PV strategy for the forward markets."""

    def __init__(self, capacity_kW):
        self._state = PVState()
        self.capacity_kW: float = capacity_kW

        self._area = None
        self._profile_generator: Optional[ForwardTradeProfileGenerator] = None

    def serialize(self):
        """Return dict with the current energy parameter values."""
        return {
            "capacity_kW": self.capacity_kW
        }

    def event_activate_energy(self, area):
        """Initialize values that are required to compute the energy values of the asset."""
        self._area = area
        self._profile_generator = ForwardTradeProfileGenerator(
            peak_kWh=convert_kW_to_kWh(self.capacity_kW, self._area.config.slot_length))

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
