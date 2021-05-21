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

from pendulum import duration, DateTime

from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from d3a_interface.read_user_profile import read_arbitrary_profile, InputProfileTypes
from d3a_interface.utils import find_object_of_same_weekday_and_time
from d3a.d3a_core.util import write_default_to_dict


class UpdateFrequencyMixin:
    def __init__(self, initial_rate, final_rate, fit_to_limit=True,
                 energy_rate_change_per_update=None, update_interval=duration(
                    minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL),
                 rate_limit_object=max):
        self.fit_to_limit = fit_to_limit
        self.initial_rate_input = initial_rate
        self.final_rate_input = final_rate
        self.energy_rate_change_per_update_input = energy_rate_change_per_update
        self.initial_rate_profile_buffer = {}
        self.final_rate_profile_buffer = {}
        self.initial_rate = {}
        self.final_rate = {}
        self.fit_to_limit = fit_to_limit
        self.energy_rate_change_per_update_profile_buffer = {}
        self._read_or_rotate_rate_profiles(GlobalConfig.start_date)

        self.energy_rate_change_per_update = {}
        self.update_interval = update_interval
        self.update_counter = {}
        self.number_of_available_updates = 0
        self.rate_limit_object = rate_limit_object

    def _read_or_rotate_rate_profiles(self, current_timestamp: DateTime,
                                      reconfigure: bool = False):
        """ Creates a new chunk of profiles if the current_timestamp is not in the profile buffers

        Args:
            current_timestamp: current time slot time
            reconfigure: Force overwriting the current profile

        """
        # TODO: this needs to be implemented to except profile UUIDs and DB connection
        if reconfigure or current_timestamp not in self.initial_rate_profile_buffer.keys():
            self.initial_rate_profile_buffer = \
                read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                       self.initial_rate_input,
                                       current_timestamp=current_timestamp)
            self.final_rate_profile_buffer = \
                read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                       self.final_rate_input,
                                       current_timestamp=current_timestamp)
            if self.fit_to_limit is False:
                self.energy_rate_change_per_update_profile_buffer = \
                    read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                           self.energy_rate_change_per_update_input,
                                           current_timestamp=current_timestamp)

    def delete_past_state_values(self, current_market_time_slot):
        to_delete = []
        for market_slot in self.initial_rate.keys():
            if market_slot < current_market_time_slot:
                to_delete.append(market_slot)
        for market_slot in to_delete:
            self.initial_rate.pop(market_slot, None)
            self.final_rate.pop(market_slot, None)
            self.energy_rate_change_per_update.pop(market_slot, None)
            self.update_counter.pop(market_slot, None)

    def _populate_profiles(self, area):
        for market in area.all_markets:
            time_slot = market.time_slot
            if self.fit_to_limit is False:
                self.energy_rate_change_per_update[time_slot] = \
                    find_object_of_same_weekday_and_time(
                        self.energy_rate_change_per_update_profile_buffer, time_slot)
            self.initial_rate[time_slot] = \
                find_object_of_same_weekday_and_time(self.initial_rate_profile_buffer,
                                                     time_slot)
            self.final_rate[time_slot] = \
                find_object_of_same_weekday_and_time(self.final_rate_profile_buffer,
                                                     time_slot)
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
        if area.current_market:
            self._read_or_rotate_rate_profiles(area.current_market.time_slot)
        self._populate_profiles(area)

    def get_updated_rate(self, time_slot):
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
            for market in strategy.area.all_markets]
        return any(should_update)

    def increment_update_counter(self, strategy, time_slot):
        if self.time_for_price_update(strategy, time_slot):
            self.update_counter[time_slot] += 1
            return True
        return False

    def time_for_price_update(self, strategy, time_slot):
        return self.elapsed_seconds(strategy) >= \
               self.update_interval.seconds * self.update_counter[time_slot]

    def set_parameters(self, area, initial_rate=None, final_rate=None,
                       energy_rate_change_per_update=None, fit_to_limit=None,
                       update_interval=None):

        update = False
        if initial_rate is not None:
            self.initial_rate_input = initial_rate
            update = True
        if final_rate is not None:
            self.final_rate_input = final_rate
            update = True
        if energy_rate_change_per_update is not None:
            self.energy_rate_change_per_update_input = energy_rate_change_per_update
            update = True
        if fit_to_limit is not None:
            self.fit_to_limit = fit_to_limit
            update = True
        if update_interval is not None:
            self.update_interval = update_interval
            update = True
        if update:
            self._read_or_rotate_rate_profiles(current_timestamp=area.current_market.time_slot
                                               if area.current_market else GlobalConfig.start_date,
                                               reconfigure=True)


class TemplateStrategyBidUpdater(UpdateFrequencyMixin):
    def reset(self, strategy):
        # decrease energy rate for each market again, except for the newly created one
        for market in strategy.area.all_markets[:-1]:
            self.update_counter[market.time_slot] = 0
            strategy.post_bids(market, self.get_updated_rate(market.time_slot))

    def update(self, market, strategy):
        if self.time_for_price_update(strategy, market.time_slot):
            if strategy.are_bids_posted(market.id):
                strategy.post_bids(market, self.get_updated_rate(market.time_slot))


class TemplateStrategyOfferUpdater(UpdateFrequencyMixin):
    def reset(self, strategy):
        for market in strategy.area.all_markets[:-1]:
            self.update_counter[market.time_slot] = 0
            strategy.update_energy_price(market, self.get_updated_rate(market.time_slot))

    def update(self, strategy):
        for market in strategy.area.all_markets:
            if self.time_for_price_update(strategy, market.time_slot):
                strategy.update_energy_price(market, self.get_updated_rate(market.time_slot))
