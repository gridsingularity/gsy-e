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

from datetime import timedelta

from d3a.d3a_core.exceptions import MarketException
from d3a.models.const import ConstSettings
from d3a.models.read_user_profile import read_arbitrary_profile
from d3a.models.read_user_profile import InputProfileTypes
from d3a.d3a_core.util import generate_market_slot_list


class UpdateFrequencyMixin:
    def __init__(self, initial_rate, final_rate, fit_to_limit=True,
                 energy_rate_change_per_update=1, update_interval=timedelta(minutes=5)):
        self.fit_to_limit = fit_to_limit
        self.initial_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                   initial_rate)
        self.final_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                 final_rate)
        self.energy_rate_change_per_update = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                                    energy_rate_change_per_update)
        self.update_interval = update_interval
        self.update_counter = 0
        self.number_of_available_updates = 0

    def _get_energy_rate_change_per_update(self):
        energy_rate_change_per_update = {}
        for slot in generate_market_slot_list():
            if self.fit_to_limit:
                energy_rate_change_per_update[slot] = \
                    (self.initial_rate[slot] - self.final_rate[slot]) / \
                    self.number_of_available_updates
            else:
                energy_rate_change_per_update[slot] = self.energy_rate_change_per_update[slot]
        return energy_rate_change_per_update

    def _calculate_number_of_available_updates_per_slot(self, strategy):
        number_of_available_updates = \
            int(strategy.area.config.slot_length.seconds / self.update_interval.seconds) - 1
        return number_of_available_updates

    def update_on_activate(self, strategy):
        assert self.update_interval.seconds >= \
               ConstSettings.GeneralSettings.UPDATE_RATE * 60
        self.number_of_available_updates = \
            self._calculate_number_of_available_updates_per_slot(strategy)
        self.energy_rate_change_per_update = \
            self._get_energy_rate_change_per_update()

    def reset_on_market_cycle(self):
        self.update_counter = 0

    def _get_updated_rate(self, market):
        updated_rate = self.initial_rate[market.time_slot] - \
                       self.energy_rate_change_per_update[market.time_slot] * self.update_counter
        return updated_rate

    def get_price_update_point(self, strategy):
        current_tick_number = strategy.area.current_tick % strategy.area.config.ticks_per_slot
        elapsed_seconds = current_tick_number * strategy.area.config.tick_length.seconds
        if elapsed_seconds >= self.update_interval.seconds * (self.update_counter+1):
            self.update_counter += 1
            return True
        else:
            return False

    def update_energy_price(self, market, strategy):
        if market.id not in strategy.offers.open.values():
            return

        for offer, iterated_market_id in strategy.offers.open.items():
            iterated_market = strategy.area.get_future_market_from_id(iterated_market_id)
            if market is None or iterated_market is None or iterated_market.id != market.id:
                continue
            try:
                iterated_market.delete_offer(offer.id)
                updated_price = round(offer.energy * self._get_updated_rate(market), 10)
                new_offer = iterated_market.offer(
                    updated_price,
                    offer.energy,
                    strategy.owner.name,
                    original_offer_price=updated_price
                )
                strategy.offers.replace(offer, new_offer, iterated_market)
            except MarketException:
                continue

    def update_market_cycle_offers(self, strategy):
        self.reset_on_market_cycle()
        for market in strategy.area.all_markets[:-1]:
            self.update_energy_price(market, strategy)

    # copied
    def set_initial_selling_rate_alternative_pricing_scheme(self, market):
        if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
            if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 1:
                self.initial_selling_rate = 0
            elif ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 2:
                self.initial_selling_rate = \
                    self.area.config.market_maker_rate[market.time_slot] * \
                    ConstSettings.IAASettings.AlternativePricing.FEED_IN_TARIFF_PERCENTAGE / 100
            elif ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 3:
                self.initial_selling_rate = \
                    self.area.config.market_maker_rate[market.time_slot]
            else:
                raise MarketException

    def update_offer(self, strategy):
        if self.get_price_update_point(strategy):
            for market in strategy.area.all_markets:
                self.update_energy_price(market, strategy)

    #############
    # BID_METHOD#
    #############
    def update_market_cycle_bids(self, strategy):
        self.reset_on_market_cycle()
        # decrease energy rate for each market again, except for the newly created one
        for market in strategy.area.all_markets[:-1]:
            self._post_bids(market, strategy)

    def _post_bids(self, market, strategy):
        existing_bids = list(strategy.get_posted_bids(market))
        for bid in existing_bids:
            assert bid.buyer == strategy.owner.name
            if bid.id in market.bids.keys():
                bid = market.bids[bid.id]
            market.delete_bid(bid.id)

            strategy.remove_bid_from_pending(bid.id, market.id)
            strategy.post_bid(market, bid.energy * self._get_updated_rate(market), bid.energy)

    def update_posted_bids_over_ticks(self, market, strategy):
        if self.get_price_update_point(strategy):
            if strategy.are_bids_posted(market.id):
                self._post_bids(market, strategy)
