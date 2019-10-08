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

from pendulum import duration

from d3a.d3a_core.exceptions import MarketException
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from d3a.models.read_user_profile import read_arbitrary_profile, InputProfileTypes
from d3a.d3a_core.util import generate_market_slot_list


class UpdateFrequencyMixin:
    def __init__(self, initial_rate, final_rate, fit_to_limit=True,
                 energy_rate_change_per_update=1, update_interval=duration(
                    minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL)):
        self.fit_to_limit = fit_to_limit
        self.initial_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                   initial_rate)
        self.final_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                 final_rate)
        self.energy_rate_change_per_update = \
            read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                   energy_rate_change_per_update)
        self.update_interval = update_interval
        self.update_counter = read_arbitrary_profile(InputProfileTypes.IDENTITY, 0)
        self.number_of_available_updates = 0

    def reassign_mixin_arguments(self, time_slot, initial_rate=None, final_rate=None,
                                 fit_to_limit=None, energy_rate_change_per_update=None,
                                 update_interval=None):
        if initial_rate is not None:
            self.initial_rate[time_slot] = initial_rate
        if final_rate is not None:
            self.final_rate[time_slot] = final_rate
        if fit_to_limit is not None:
            self.fit_to_limit = fit_to_limit
        if energy_rate_change_per_update is not None:
            self.energy_rate_change_per_update[time_slot] = \
                energy_rate_change_per_update
        if update_interval is not None:
            self.update_interval = update_interval

        self.update_on_activate()

    def _set_or_update_energy_rate_change_per_update(self):
        energy_rate_change_per_update = {}
        for slot in generate_market_slot_list():
            if self.fit_to_limit:
                energy_rate_change_per_update[slot] = \
                    (self.initial_rate[slot] - self.final_rate[slot]) / \
                    self.number_of_available_updates
            else:
                energy_rate_change_per_update[slot] = self.energy_rate_change_per_update[slot]
        self.energy_rate_change_per_update = energy_rate_change_per_update

    @property
    def _calculate_number_of_available_updates_per_slot(self):
        number_of_available_updates = \
            int(GlobalConfig.slot_length.seconds / self.update_interval.seconds) - 1
        return number_of_available_updates

    def update_on_activate(self):
        assert self.update_interval.seconds >= \
               ConstSettings.GeneralSettings.MIN_UPDATE_INTERVAL * 60
        self.number_of_available_updates = \
            self._calculate_number_of_available_updates_per_slot
        self._set_or_update_energy_rate_change_per_update()

    def get_updated_rate(self, time_slot):
        calculated_rate = \
            self.initial_rate[time_slot] - \
            self.energy_rate_change_per_update[time_slot] * self.update_counter[time_slot]
        updated_rate = max(calculated_rate, self.final_rate[time_slot])
        return updated_rate

    def get_price_update_point(self, strategy, time_slot):
        current_tick_number = strategy.area.current_tick % strategy.area.config.ticks_per_slot
        elapsed_seconds = current_tick_number * strategy.area.config.tick_length.seconds
        if elapsed_seconds >= self.update_interval.seconds * (self.update_counter[time_slot]+1):
            self.update_counter[time_slot] += 1
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
                updated_price = round(offer.energy * self.get_updated_rate(market.time_slot), 10)
                new_offer = iterated_market.offer(
                    updated_price,
                    offer.energy,
                    strategy.owner.name,
                    original_offer_price=updated_price,
                    seller_origin=offer.seller_origin
                )
                strategy.offers.replace(offer, new_offer, iterated_market)
            except MarketException:
                continue

    def update_market_cycle_offers(self, strategy):
        for market in strategy.area.all_markets[:-1]:
            self.update_counter[market.time_slot] = 0
            self.update_energy_price(market, strategy)

    def update_offer(self, strategy):
        for market in strategy.area.all_markets:
            if self.get_price_update_point(strategy, market.time_slot):
                self.update_energy_price(market, strategy)

    def update_market_cycle_bids(self, strategy):
        # decrease energy rate for each market again, except for the newly created one
        for market in strategy.area.all_markets[:-1]:
            self.update_counter[market.time_slot] = 0
            self._post_bids(market, strategy)

    def _post_bids(self, market, strategy):
        existing_bids = list(strategy.get_posted_bids(market))
        for bid in existing_bids:
            assert bid.buyer == strategy.owner.name
            if bid.id in market.bids.keys():
                bid = market.bids[bid.id]
            market.delete_bid(bid.id)

            strategy.remove_bid_from_pending(bid.id, market.id)
            strategy.post_bid(market, bid.energy * self.get_updated_rate(market.time_slot),
                              bid.energy, buyer_origin=bid.buyer_origin)

    def update_posted_bids_over_ticks(self, market, strategy):
        if self.get_price_update_point(strategy, market.time_slot):
            if strategy.are_bids_posted(market.id):
                self._post_bids(market, strategy)
