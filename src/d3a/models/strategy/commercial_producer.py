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
import logging

from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.utils import convert_str_to_pendulum_in_dict, convert_pendulum_to_str_in_dict
from gsy_framework.utils import find_object_of_same_weekday_and_time
from gsy_framework.validators import CommercialProducerValidator

from d3a.gsy_core.device_registry import DeviceRegistry
from d3a.gsy_core.exceptions import MarketException
from d3a.gsy_core.global_objects_singleton import global_objects
from d3a.models.strategy import BaseStrategy, INF_ENERGY


class CommercialStrategy(BaseStrategy):
    parameters = ("energy_rate",)

    def __init__(self, energy_rate=None):
        CommercialProducerValidator.validate(energy_rate=energy_rate)
        super().__init__()
        self.energy_rate_input = energy_rate
        self.energy_rate = None
        self.energy_per_slot_kWh = INF_ENERGY

    def event_activate(self, **kwargs):
        self._read_or_rotate_profiles()

    def _read_or_rotate_profiles(self, reconfigure=False):
        if self.energy_rate_input is None:
            self.energy_rate = self.area.config.market_maker_rate
        else:
            self.energy_rate = \
                global_objects.profiles_handler.rotate_profile(
                    InputProfileTypes.IDENTITY,
                    self.energy_rate if self.energy_rate else self.energy_rate_input)

    def _markets_to_offer_on_activate(self):
        return self.area.all_markets

    def place_initial_offers(self):
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
        energy_rate = find_object_of_same_weekday_and_time(self.energy_rate, market.time_slot)
        try:
            offer = market.offer(
                self.energy_per_slot_kWh * energy_rate,
                self.energy_per_slot_kWh,
                self.owner.name,
                original_price=self.energy_per_slot_kWh * energy_rate,
                seller_origin=self.owner.name,
                seller_origin_id=self.owner.uuid,
                seller_id=self.owner.uuid
            )

            self.offers.post(offer, market.id)
        except MarketException:
            logging.error(f"Offer posted with negative energy rate {energy_rate}."
                          f"Posting offer with zero energy rate instead.")

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

    def get_state(self):
        return {"energy_rate": convert_pendulum_to_str_in_dict(self.energy_rate)}

    def restore_state(self, saved_state):
        self.energy_rate.update(convert_str_to_pendulum_in_dict(saved_state["energy_rate"]))
