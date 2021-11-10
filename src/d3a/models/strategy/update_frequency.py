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

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.utils import find_object_of_same_weekday_and_time
from pendulum import duration

from d3a.d3a_core.global_objects_singleton import global_objects
from d3a.d3a_core.util import write_default_to_dict, is_time_slot_in_past_markets


class UpdateFrequencyMixin:
    def __init__(self, initial_rate, final_rate, fit_to_limit=True,
                 energy_rate_change_per_update=None, update_interval=duration(
                    minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL),
                 rate_limit_object=max):
        self.fit_to_limit = fit_to_limit

        # initial input values (currently of type float)
        self.initial_rate_input = initial_rate
        self.final_rate_input = final_rate
        self.energy_rate_change_per_update_input = energy_rate_change_per_update

        # buffer of populated input values Dict[DateTime, float]
        self.initial_rate_profile_buffer = {}
        self.final_rate_profile_buffer = {}
        self.energy_rate_change_per_update_profile_buffer = {}

        # dicts that are used for price calculations, contain only all_markets Dict[DatTime, float]
        self.initial_rate = {}
        self.final_rate = {}
        self.energy_rate_change_per_update = {}

        self._read_or_rotate_rate_profiles()

        self.update_interval = update_interval
        self.update_counter = {}
        self.number_of_available_updates = 0
        self.rate_limit_object = rate_limit_object

    def _read_or_rotate_rate_profiles(self):
        """ Creates a new chunk of profiles if the current_timestamp is not in the profile buffers
        """
        # TODO: this needs to be implemented to except profile UUIDs and DB connection
        self.initial_rate_profile_buffer = global_objects.profiles_handler.rotate_profile(
            InputProfileTypes.IDENTITY, self.initial_rate_input)
        self.final_rate_profile_buffer = global_objects.profiles_handler.rotate_profile(
            InputProfileTypes.IDENTITY, self.final_rate_input)
        if self.fit_to_limit is False:
            self.energy_rate_change_per_update_profile_buffer = (
                global_objects.profiles_handler.rotate_profile(
                    InputProfileTypes.IDENTITY, self.energy_rate_change_per_update_input)
            )

    def delete_past_state_values(self, current_market_time_slot):
        to_delete = []
        for market_slot in self.initial_rate.keys():
            if is_time_slot_in_past_markets(market_slot, current_market_time_slot):
                to_delete.append(market_slot)
        for market_slot in to_delete:
            self.initial_rate.pop(market_slot, None)
            self.final_rate.pop(market_slot, None)
            self.energy_rate_change_per_update.pop(market_slot, None)
            self.update_counter.pop(market_slot, None)

    @staticmethod
    def get_all_markets(area):
        return area.all_markets

    def _populate_profiles(self, area):
        for market in self.get_all_markets(area):
            time_slot = market.time_slot
            if self.fit_to_limit is False:
                self.energy_rate_change_per_update[time_slot] = (
                    find_object_of_same_weekday_and_time(
                        self.energy_rate_change_per_update_profile_buffer, time_slot)
                )
            self.initial_rate[time_slot] = find_object_of_same_weekday_and_time(
                self.initial_rate_profile_buffer, time_slot)
            self.final_rate[time_slot] = find_object_of_same_weekday_and_time(
                self.final_rate_profile_buffer, time_slot)
            self._set_or_update_energy_rate_change_per_update(market.time_slot)
            write_default_to_dict(self.update_counter, market.time_slot, 0)

    def reassign_mixin_arguments(self, time_slot, initial_rate=None, final_rate=None,
                                 fit_to_limit=None, energy_rate_change_per_update=None,
                                 update_interval=None):
        if initial_rate is not None:
            self.initial_rate_profile_buffer[time_slot] = initial_rate
        if final_rate is not None:
            self.final_rate_profile_buffer[time_slot] = final_rate
        if fit_to_limit is not None:
            self.fit_to_limit = fit_to_limit
        if energy_rate_change_per_update is not None:
            self.energy_rate_change_per_update_profile_buffer[time_slot] = \
                energy_rate_change_per_update
        if update_interval is not None:
            self.update_interval = update_interval

        self.number_of_available_updates = \
            self._calculate_number_of_available_updates_per_slot
        self._set_or_update_energy_rate_change_per_update(time_slot)

    def _set_or_update_energy_rate_change_per_update(self, time_slot):
        energy_rate_change_per_update = {}
        if self.fit_to_limit:
            energy_rate_change_per_update[time_slot] = \
                (find_object_of_same_weekday_and_time(
                    self.initial_rate_profile_buffer, time_slot) -
                 find_object_of_same_weekday_and_time(
                     self.final_rate_profile_buffer, time_slot)) / \
                self.number_of_available_updates
        else:
            if self.rate_limit_object is min:
                energy_rate_change_per_update[time_slot] = \
                    -1 * find_object_of_same_weekday_and_time(
                        self.energy_rate_change_per_update_profile_buffer, time_slot)
            elif self.rate_limit_object is max:
                energy_rate_change_per_update[time_slot] = \
                    find_object_of_same_weekday_and_time(
                        self.energy_rate_change_per_update_profile_buffer, time_slot)
        self.energy_rate_change_per_update.update(energy_rate_change_per_update)

    @property
    def _calculate_number_of_available_updates_per_slot(self):
        number_of_available_updates = \
            max(int((GlobalConfig.slot_length.seconds / self.update_interval.seconds) - 1), 1)
        return number_of_available_updates

    def update_and_populate_price_settings(self, area):
        assert ConstSettings.GeneralSettings.MIN_UPDATE_INTERVAL * 60 <= \
               self.update_interval.seconds < GlobalConfig.slot_length.seconds

        self.number_of_available_updates = \
            self._calculate_number_of_available_updates_per_slot

        self._populate_profiles(area)

    def get_updated_rate(self, time_slot):
        """Compute the rate for offers/bids at a specific time slot."""
        calculated_rate = \
            self.initial_rate[time_slot] - \
            self.energy_rate_change_per_update[time_slot] * self.update_counter[time_slot]
        updated_rate = self.rate_limit_object(calculated_rate, self.final_rate[time_slot])
        return updated_rate

    @staticmethod
    def elapsed_seconds(strategy):
        current_tick_number = strategy.area.current_tick % strategy.area.config.ticks_per_slot
        return current_tick_number * strategy.area.config.tick_length.seconds

    def increment_update_counter_all_markets(self, strategy):
        should_update = [
            self.increment_update_counter(strategy, market.time_slot)
            for market in self.get_all_markets(strategy.area)
        ]
        return any(should_update)

    def increment_update_counter(self, strategy, time_slot):
        """Increment the counter of the number of times in which prices have been updated."""
        if self.time_for_price_update(strategy, time_slot):
            self.update_counter[time_slot] += 1
            return True
        return False

    def time_for_price_update(self, strategy, time_slot):
        """Check if the prices of bids/offers should be updated."""
        return self.elapsed_seconds(strategy) >= (
            self.update_interval.seconds * self.update_counter[time_slot])

    def set_parameters(self, *, initial_rate=None, final_rate=None,
                       energy_rate_change_per_update=None, fit_to_limit=None,
                       update_interval=None):

        should_update = False
        if initial_rate is not None:
            self.initial_rate_input = initial_rate
            should_update = True
        if final_rate is not None:
            self.final_rate_input = final_rate
            should_update = True
        if energy_rate_change_per_update is not None:
            self.energy_rate_change_per_update_input = energy_rate_change_per_update
            should_update = True
        if fit_to_limit is not None:
            self.fit_to_limit = fit_to_limit
            should_update = True
        if update_interval is not None:
            self.update_interval = update_interval
            should_update = True
        if should_update:
            self._read_or_rotate_rate_profiles()


class TemplateStrategyBidUpdater(UpdateFrequencyMixin):
    def reset(self, strategy):
        """Reset the price of all bids to use their initial rate."""
        # decrease energy rate for each market again, except for the newly created one
        for market in self.get_all_markets(strategy.area)[:-1]:
            self.update_counter[market.time_slot] = 0
            strategy.update_bid_rates(market, self.get_updated_rate(market.time_slot))

    def update(self, market, strategy):
        """Update the price of existing bids to reflect the new rates."""
        if self.time_for_price_update(strategy, market.time_slot):
            if strategy.are_bids_posted(market.id):
                strategy.update_bid_rates(market, self.get_updated_rate(market.time_slot))


class TemplateStrategyOfferUpdater(UpdateFrequencyMixin):
    def reset(self, strategy):
        """Reset the price of all offers based to use their initial rate."""
        for market in self.get_all_markets(strategy.area)[:-1]:
            self.update_counter[market.time_slot] = 0
            strategy.update_offer_rates(market, self.get_updated_rate(market.time_slot))

    def update(self, market, strategy):
        """Update the price of existing offers to reflect the new rates."""
        if self.time_for_price_update(strategy, market.time_slot):
            if strategy.are_offers_posted(market.id):
                strategy.update_offer_rates(market, self.get_updated_rate(market.time_slot))
