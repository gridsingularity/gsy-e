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
from typing import TYPE_CHECKING, Callable, List, Dict

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.utils import (
    get_from_profile_same_weekday_and_time,
    is_time_slot_in_simulation_duration,
)
from pendulum import duration, DateTime, Duration

import gsy_e.constants
from gsy_e.gsy_e_core.global_objects_singleton import global_objects
from gsy_e.gsy_e_core.util import write_default_to_dict, is_time_slot_in_past_markets

if TYPE_CHECKING:
    from gsy_e.models.area import Area
    from gsy_e.models.market.one_sided import OneSidedMarket
    from gsy_e.models.market.two_sided import TwoSidedMarket
    from gsy_e.models.strategy import BidEnabledStrategy, BaseStrategy


class TemplateStrategyUpdaterInterface:
    """Interface for the updater of orders for template strategies"""

    def update_and_populate_price_settings(self, area: "Area") -> None:
        """Update the price settings. Usually called during the market cycle event"""

    def increment_update_counter_all_markets(self, strategy: "BaseStrategy") -> None:
        """Increment the update counter for all markets. Usually called during the tick event"""

    def set_parameters(  # pylint: disable=too-many-arguments
        self,
        *,
        initial_rate: float = None,
        final_rate: float = None,
        energy_rate_change_per_update: float = None,
        fit_to_limit: bool = None,
        update_interval: int = None
    ) -> None:
        """Update the parameters of the class on the fly."""

    def reset(self, strategy: "BaseStrategy") -> None:
        """Reset the price of all orders based to use their initial rate."""

    def update(self, market: "OneSidedMarket", strategy: "BaseStrategy") -> None:
        """Update the price of existing orders to reflect the new rates."""

    def delete_past_state_values(self, current_market_time_slot: DateTime) -> None:
        """Delete irrelevant values from buffers for unneeded markets."""


class TemplateStrategyUpdaterBase(TemplateStrategyUpdaterInterface):
    """Manage template strategy bid / offer posting. Updates periodically the energy rate
    of the posted bids or offers. Base class"""

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        initial_rate: float,
        final_rate: float,
        fit_to_limit: bool = True,
        energy_rate_change_per_update: float = None,
        update_interval: Duration = duration(
            minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL
        ),
        rate_limit_object: Callable = max,
    ):
        # pylint: disable=too-many-arguments
        self.fit_to_limit = fit_to_limit

        # initial input values (currently of type float)
        self.initial_rate_input = initial_rate
        self.final_rate_input = final_rate
        self.energy_rate_change_per_update_input = energy_rate_change_per_update

        # buffer of populated input values Dict[DateTime, float]
        self.initial_rate_profile_buffer = {}
        self.final_rate_profile_buffer = {}
        self.energy_rate_change_per_update_profile_buffer = {}

        # dicts that are used for price calculations, contain only
        # all_markets Dict[DateTime, float]
        self.initial_rate = {}
        self.final_rate = {}
        self.energy_rate_change_per_update = {}

        self._read_or_rotate_rate_profiles()

        self.update_interval = update_interval
        self.update_counter = {}

        # Keeps track of the elapsed seconds at the time of insertion of
        # the slot (relevant to future markets)
        self.market_slot_added_time_mapping: Dict[DateTime:int] = {}

        self.number_of_available_updates = 0
        self.rate_limit_object = rate_limit_object

    def serialize(self):
        """Return dict with configuration parameters."""
        return {"fit_to_limit": self.fit_to_limit, "update_interval": self.update_interval}

    def _read_or_rotate_rate_profiles(self) -> None:
        """
        Creates a new chunk of profiles if the current_timestamp is not in the profile buffers
        """
        self.initial_rate_profile_buffer = global_objects.profiles_handler.rotate_profile(
            profile_type=InputProfileTypes.IDENTITY,
            profile=(
                self.initial_rate_profile_buffer
                if self.initial_rate_profile_buffer
                else self.initial_rate_input
            ),
            input_profile_path=self.initial_rate_input,
        )
        self.final_rate_profile_buffer = global_objects.profiles_handler.rotate_profile(
            profile_type=InputProfileTypes.IDENTITY,
            profile=(
                self.final_rate_profile_buffer
                if self.final_rate_profile_buffer
                else self.final_rate_input
            ),
            input_profile_path=self.final_rate_input,
        )
        if self.fit_to_limit is False:
            self.energy_rate_change_per_update_profile_buffer = (
                global_objects.profiles_handler.rotate_profile(
                    InputProfileTypes.IDENTITY, self.energy_rate_change_per_update_input
                )
            )

    def _delete_market_slot_data(self, market_time_slot: DateTime) -> None:
        self.initial_rate.pop(market_time_slot, None)
        self.final_rate.pop(market_time_slot, None)
        self.energy_rate_change_per_update.pop(market_time_slot, None)
        self.update_counter.pop(market_time_slot, None)
        self.market_slot_added_time_mapping.pop(market_time_slot, None)

    def delete_past_state_values(self, current_market_time_slot: DateTime) -> None:
        """Delete values from buffers before the current_market_time_slot"""
        to_delete = []
        for market_slot in self.initial_rate:
            if is_time_slot_in_past_markets(market_slot, current_market_time_slot):
                to_delete.append(market_slot)
        for market_slot in to_delete:
            self._delete_market_slot_data(market_slot)

    @staticmethod
    def get_all_markets(area: "Area") -> List["OneSidedMarket"]:
        """Get list of available markets. Defaults to only the spot market."""
        return [area.spot_market]

    @staticmethod
    def _get_all_time_slots(area: "Area") -> List[DateTime]:
        """Get list of available time slots. Defaults to only the spot market time slot."""
        if not area or not area.spot_market:
            return []
        return [area.spot_market.time_slot]

    def _populate_profiles(self, area: "Area") -> None:
        for time_slot in self._get_all_time_slots(area):
            if not is_time_slot_in_simulation_duration(time_slot, area.config):
                continue
            if self.fit_to_limit is False:
                self.energy_rate_change_per_update[time_slot] = (
                    get_from_profile_same_weekday_and_time(
                        self.energy_rate_change_per_update_profile_buffer, time_slot
                    )
                )
            initial_rate = get_from_profile_same_weekday_and_time(
                self.initial_rate_profile_buffer, time_slot
            )
            final_rate = get_from_profile_same_weekday_and_time(
                self.final_rate_profile_buffer, time_slot
            )

            if initial_rate is None or final_rate is None:
                logging.warning(
                    "Failed to read initial or final rate profile for simulation %s and area %s. "
                    "Reloading profiles from the database.",
                    gsy_e.constants.CONFIGURATION_ID,
                    area.uuid,
                )
                self._read_or_rotate_rate_profiles()
                initial_rate = get_from_profile_same_weekday_and_time(
                    self.initial_rate_profile_buffer, time_slot
                )
                final_rate = get_from_profile_same_weekday_and_time(
                    self.final_rate_profile_buffer, time_slot
                )

            # Hackathon TODO: get rid of self.initial_rate, self.final_rate, self.update_counter
            # and self.market_slot_added_time_mapping in favor of one object
            # that keeps track of time_slot: attributes
            self.initial_rate[time_slot] = initial_rate
            self.final_rate[time_slot] = final_rate

            self._set_or_update_energy_rate_change_per_update(time_slot)
            write_default_to_dict(self.update_counter, time_slot, 0)

            # todo: homogenize the calculation of elapsed seconds for spot and future markets
            self._add_slot_to_mapping(area, time_slot)

    def _add_slot_to_mapping(self, area, time_slot):
        """keep track of the elapsed time of simulation at the addition of a new slot."""
        if time_slot not in self.market_slot_added_time_mapping:
            elapsed_seconds = self._elapsed_seconds(area)
            self.market_slot_added_time_mapping[time_slot] = elapsed_seconds

    def _set_or_update_energy_rate_change_per_update(self, time_slot: DateTime) -> None:
        energy_rate_change_per_update = {}
        if self.fit_to_limit:
            initial_rate = get_from_profile_same_weekday_and_time(
                self.initial_rate_profile_buffer, time_slot
            )
            final_rate = get_from_profile_same_weekday_and_time(
                self.final_rate_profile_buffer, time_slot
            )
            energy_rate_change_per_update[time_slot] = (
                initial_rate - final_rate
            ) / self.number_of_available_updates
        else:
            if self.rate_limit_object is min:
                energy_rate_change_per_update[time_slot] = (
                    -1
                    * get_from_profile_same_weekday_and_time(
                        self.energy_rate_change_per_update_profile_buffer, time_slot
                    )
                )
            elif self.rate_limit_object is max:
                energy_rate_change_per_update[time_slot] = get_from_profile_same_weekday_and_time(
                    self.energy_rate_change_per_update_profile_buffer, time_slot
                )
        self.energy_rate_change_per_update.update(energy_rate_change_per_update)

    @property
    def _time_slot_duration_in_seconds(self) -> int:
        return GlobalConfig.slot_length.seconds

    @property
    def _calculate_number_of_available_updates_per_slot(self) -> int:
        number_of_available_updates = max(
            int((self._time_slot_duration_in_seconds / self.update_interval.seconds) - 1), 1
        )
        return number_of_available_updates

    def update_and_populate_price_settings(self, area: "Area") -> None:
        """Populate the price profiles for every available time slot."""
        self._read_or_rotate_rate_profiles()
        # Handling the case where future markets are disabled during a simulation.
        if self._time_slot_duration_in_seconds <= 0:
            return

        assert (
            ConstSettings.GeneralSettings.MIN_UPDATE_INTERVAL * 60
            <= self.update_interval.seconds
            < self._time_slot_duration_in_seconds
        )

        self.number_of_available_updates = self._calculate_number_of_available_updates_per_slot

        self._populate_profiles(area)

    def get_updated_rate(self, time_slot: DateTime) -> float:
        """Compute the rate for offers/bids at a specific time slot."""
        calculated_rate = (
            self.initial_rate[time_slot]
            - self.energy_rate_change_per_update[time_slot] * self.update_counter[time_slot]
        )
        updated_rate = self.rate_limit_object(calculated_rate, self.final_rate[time_slot])
        return updated_rate

    @staticmethod
    def _elapsed_seconds(area: "Area") -> int:
        """Return the elapsed seconds since the very beginning of the simulation."""
        return area.current_tick * area.config.tick_length.seconds

    def _elapsed_seconds_per_slot(self, area: "Area") -> int:
        """Return the elapsed seconds since the beginning of the market slot."""
        current_tick_number = area.current_tick % (
            self._time_slot_duration_in_seconds / area.config.tick_length.seconds
        )
        return current_tick_number * area.config.tick_length.seconds

    def increment_update_counter_all_markets(self, strategy: "BaseStrategy") -> None:
        """Update method of the class. Should be called on each tick and increments the
        update counter in order to validate whether an update in the posted energy rates
        is required."""
        for time_slot in self._get_all_time_slots(strategy.area):
            self.increment_update_counter(strategy, time_slot)

    def increment_update_counter(self, strategy: "BaseStrategy", time_slot) -> None:
        """Increment the counter of the number of times in which prices have been updated."""
        if self.time_for_price_update(strategy, time_slot):
            self.update_counter[time_slot] += 1

    def time_for_price_update(self, strategy: "BaseStrategy", time_slot: DateTime) -> bool:
        """Check if the prices of bids/offers should be updated."""
        return self._elapsed_seconds_per_slot(strategy.area) >= (
            self.update_interval.seconds * self.update_counter[time_slot]
        )

    def set_parameters(
        self,
        *,
        initial_rate: float = None,
        final_rate: float = None,
        energy_rate_change_per_update: float = None,
        fit_to_limit: bool = None,
        update_interval: int = None
    ) -> None:
        """Update the parameters of the class without the need to destroy and recreate
        the object."""
        if initial_rate is not None:
            self.initial_rate_input = initial_rate
        if final_rate is not None:
            self.final_rate_input = final_rate
        if energy_rate_change_per_update is not None:
            self.energy_rate_change_per_update_input = energy_rate_change_per_update
        if fit_to_limit is not None:
            self.fit_to_limit = fit_to_limit
        if update_interval is not None:
            self.update_interval = update_interval
        self._read_or_rotate_rate_profiles()

    def reset(self, strategy: "BaseStrategy") -> None:
        raise NotImplementedError

    def update(self, market: "OneSidedMarket", strategy: "BaseStrategy") -> None:
        raise NotImplementedError


class TemplateStrategyBidUpdater(TemplateStrategyUpdaterBase):
    """Manage bids posted by template strategies. Update bids periodically."""

    def reset(self, strategy: "BidEnabledStrategy") -> None:
        """Reset the price of all bids to use their initial rate."""
        # decrease energy rate for each market again, except for the newly created one
        for market in self.get_all_markets(strategy.area):
            self.update_counter[market.time_slot] = 0
            strategy.update_bid_rates(market, self.get_updated_rate(market.time_slot))

    def update(self, market: "TwoSidedMarket", strategy: "BidEnabledStrategy") -> None:
        """Update the price of existing bids to reflect the new rates."""
        if self.time_for_price_update(strategy, market.time_slot):
            if strategy.are_bids_posted(market.id):
                strategy.update_bid_rates(market, self.get_updated_rate(market.time_slot))

    def serialize(self):
        return {
            **super().serialize(),
            "initial_buying_rate": self.initial_rate_input,
            "final_buying_rate": self.final_rate_input,
            "energy_rate_increase_per_update": self.energy_rate_change_per_update_input,
        }


class TemplateStrategyOfferUpdater(TemplateStrategyUpdaterBase):
    """Manage offers posted by template strategies. Update offers periodically."""

    def reset(self, strategy: "BaseStrategy") -> None:
        """Reset the price of all offers based to use their initial rate."""
        for market in self.get_all_markets(strategy.area):
            self.update_counter[market.time_slot] = 0
            strategy.update_offer_rates(market, self.get_updated_rate(market.time_slot))

    def update(self, market: "OneSidedMarket", strategy: "BaseStrategy") -> None:
        """Update the price of existing offers to reflect the new rates."""
        if self.time_for_price_update(strategy, market.time_slot):
            if strategy.are_offers_posted(market.id):
                strategy.update_offer_rates(market, self.get_updated_rate(market.time_slot))

    def serialize(self):
        return {
            **super().serialize(),
            "initial_selling_rate": self.initial_rate_input,
            "final_selling_rate": self.final_rate_input,
            "energy_rate_decrease_per_update": self.energy_rate_change_per_update_input,
        }
