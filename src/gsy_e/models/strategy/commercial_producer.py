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

import logging

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import TraderDetails
from gsy_framework.utils import convert_pendulum_to_str_in_dict, convert_str_to_pendulum_in_dict
from gsy_framework.validators import CommercialProducerValidator

from gsy_e.gsy_e_core.device_registry import DeviceRegistry
from gsy_e.gsy_e_core.exceptions import MarketException
from gsy_e.models.base import AssetType
from gsy_e.models.strategy import INF_ENERGY, BaseStrategy
from gsy_e.models.strategy.strategy_profile import StrategyProfile


class CommercialStrategy(BaseStrategy):
    """Strategy class for commercial energy producer that can sell an infinite amount of energy."""

    def __init__(self, energy_rate=None):
        super().__init__()
        self.energy_per_slot_kWh = INF_ENERGY

        if energy_rate is None:
            energy_rate = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE
        self._sell_energy_profile = StrategyProfile(input_energy_rate=energy_rate)
        CommercialProducerValidator.validate(energy_rate=self._sell_energy_profile.profile)

    @property
    def energy_rate(self):
        # This method exists for backward compatibility.
        """Return sell energy profile of the asset."""
        return self._sell_energy_profile.profile

    def serialize(self):
        return {"energy_rate": self._sell_energy_profile.input_energy_rate}

    @property
    def state(self):
        raise AttributeError("Commercial Producer has no state.")

    def event_activate(self, **kwargs):
        self._read_or_rotate_profiles()

    def _read_or_rotate_profiles(self, reconfigure=False):
        self._sell_energy_profile.read_or_rotate_profiles(reconfigure=reconfigure)

    def _markets_to_offer_on_activate(self):
        return self.area.all_markets

    def place_initial_offers(self):
        """Placing initial offers on newly opened markets."""
        # That's usually an init function but the markets aren't open during the init call
        for market in self._markets_to_offer_on_activate():
            self.offer_energy(market)
        for market in self.area.balancing_markets:
            self._offer_balancing_energy(market)

    def event_market_cycle(self):
        self._read_or_rotate_profiles()
        if not self.area.last_past_market:
            # Post new offers only on first time_slot:
            self.place_initial_offers()
        else:
            # Post new offers
            market = self.area.all_markets[-1]
            self.offer_energy(market)

            if len(self.area.balancing_markets) > 0:
                balancing_market = self.area.balancing_markets[-1]
                self._offer_balancing_energy(balancing_market)

    def offer_energy(self, market):
        """Method for offering energy on a market."""
        energy_rate = self._sell_energy_profile.get_value(market.time_slot)
        try:
            offer = market.offer(
                self.energy_per_slot_kWh * energy_rate,
                self.energy_per_slot_kWh,
                TraderDetails(self.owner.name, self.owner.uuid, self.owner.name, self.owner.uuid),
                original_price=self.energy_per_slot_kWh * energy_rate,
            )

            self.offers.post(offer, market.id)
        except MarketException:
            logging.error(
                "Offer posted with negative energy rate %s."
                "Posting offer with zero energy rate instead.",
                energy_rate,
            )

    def _offer_balancing_energy(self, market):
        if not self._is_eligible_for_balancing_market:
            return

        # The second tuple member in the device registry is the balancing supply rate
        # TODO: Consider adding infinite balancing demand offers in addition to supply, if we
        # assume that CommercialProducer is a grid connection and not a power plant.
        balancing_supply_rate = DeviceRegistry.REGISTRY[self.owner.name][1]

        offer = market.balancing_offer(
            self.energy_per_slot_kWh * balancing_supply_rate,
            self.energy_per_slot_kWh,
            TraderDetails(self.owner.name, self.owner.uuid, self.owner.name, self.owner.uuid),
        )
        self.offers.post(offer, market.id)

    def get_state(self):
        return {"energy_rate": convert_pendulum_to_str_in_dict(self._sell_energy_profile.profile)}

    def restore_state(self, saved_state):
        self._sell_energy_profile.profile = convert_str_to_pendulum_in_dict(
            saved_state["energy_rate"]
        )

    @property
    def asset_type(self):
        return AssetType.PRODUCER
