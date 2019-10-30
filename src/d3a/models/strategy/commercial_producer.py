"""
Copyright 2018 Grid Singularity
This file is part of D3A.

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
import sys

from d3a.models.strategy import BaseStrategy
from d3a.d3a_core.device_registry import DeviceRegistry
from d3a.models.read_user_profile import read_arbitrary_profile, InputProfileTypes
from d3a_interface.device_validator import validate_commercial_producer


class CommercialStrategy(BaseStrategy):
    parameters = ('energy_rate',)

    def __init__(self, energy_rate=None):
        validate_commercial_producer(energy_rate=energy_rate)
        super().__init__()
        self.energy_rate = energy_rate
        self.energy_per_slot_kWh = int(sys.maxsize)

    def event_activate(self):
        self.energy_rate = self.area.config.market_maker_rate if self.energy_rate is None \
            else read_arbitrary_profile(InputProfileTypes.IDENTITY, self.energy_rate)

    def _markets_to_offer_on_activate(self):
        return self.area.all_markets

    def place_initial_offers(self):
        # That's usually an init function but the markets aren't open during the init call
        for market in self._markets_to_offer_on_activate():
            self.offer_energy(market)
        for market in self.area.balancing_markets:
            self._offer_balancing_energy(market)

    def event_market_cycle(self):
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
        energy_rate = self.energy_rate[market.time_slot]
        offer = market.offer(
            self.energy_per_slot_kWh * energy_rate,
            self.energy_per_slot_kWh,
            self.owner.name,
            original_offer_price=self.energy_per_slot_kWh * energy_rate,
            seller_origin=self.owner.name
        )

        self.offers.post(offer, market.id)

    def _offer_balancing_energy(self, market):
        if not self.is_eligible_for_balancing_market:
            return

        # The second tuple member in the device registry is the balancing supply rate
        # TODO: Consider adding infinite balancing demand offers in addition to supply, if we
        # assume that CommercialProducer is a grid connection and not a power plant.
        balancing_supply_rate = DeviceRegistry.REGISTRY[self.owner.name][1]

        offer = market.balancing_offer(
            self.energy_per_slot_kWh * balancing_supply_rate,
            self.energy_per_slot_kWh,
            self.owner.name
        )
        self.offers.post(offer, market.id)
