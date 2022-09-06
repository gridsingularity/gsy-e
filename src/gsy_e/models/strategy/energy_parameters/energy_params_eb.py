from typing import Optional

import pendulum
from gsy_framework.utils import convert_kW_to_kWh

from gsy_e.models.state import LoadState
from gsy_e.models.strategy.energy_parameters.forward_profile import ForwardTradeProfileGenerator


class LoadSSPEnergyParameters:
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

    def event_traded_energy(self, energy_kWh, market_slot: pendulum.DateTime, product_type):
        """
        When a trade happens, we want to split the energy through the entire year following a
        standard solar profile.
        """
        assert self._profile_generator is not None
        # Create a new profile that spreads the trade energy across multiple slots. The values
        # of this new profile are obtained by scaling the values of the standard solar profile
        return self._profile_generator.generate_trade_profile(
            energy_kWh=energy_kWh,
            market_slot=market_slot,
            product_type=product_type)
