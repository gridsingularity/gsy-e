"""
Copyright 2018 Grid Singularity
This file is part of D3A.
This program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not,
see <http://www.gnu.org/licenses/>.
"""
from logging import getLogger
from typing import Dict, Union

from d3a_interface.constants_limits import ConstSettings
from d3a_interface.device_validator import validate_load_device_price
from d3a_interface.read_user_profile import read_arbitrary_profile, InputProfileTypes
from d3a_interface.utils import find_object_of_same_weekday_and_time, key_in_dict_and_not_none
from numpy import random
from pendulum import duration

from d3a import constants
from d3a.constants import FLOATING_POINT_TOLERANCE, DEFAULT_PRECISION
from d3a.d3a_core.exceptions import D3AException
from d3a.d3a_core.exceptions import MarketException
from d3a.d3a_core.util import get_market_maker_rate_from_config
from d3a.models.state import HomeMeterState
from d3a.models.strategy import BidEnabledStrategy
from d3a.models.strategy.update_frequency import (
    TemplateStrategyBidUpdater, TemplateStrategyOfferUpdater)

log = getLogger(__name__)


class HomeMeterStrategy(BidEnabledStrategy):
    """Class defining a strategy for Home Meter devices."""

    # The `parameters` set is used to decide which fields will be added to the serialized
    # representation of the Leaf object that uses this strategy (see AreaEncoder).
    parameters = (
        "home_meter_profile",
        # Energy production parameters
        "initial_selling_rate", "final_selling_rate", "energy_rate_decrease_per_update",
        # Energy consumption parameters
        "initial_buying_rate", "final_buying_rate", "energy_rate_increase_per_update",
        # Common parameters
        "fit_to_limit", "update_interval", "use_market_maker_rate")

    def __init__(
            self,
            home_meter_profile: Union[str, Dict[int, float], Dict[str, float]],
            initial_selling_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
            final_selling_rate: float = ConstSettings.HomeMeterSettings.SELLING_RATE_RANGE.final,
            energy_rate_decrease_per_update: Union[float, None] = None,
            initial_buying_rate: float = ConstSettings.HomeMeterSettings.BUYING_RATE_RANGE.initial,
            final_buying_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
            energy_rate_increase_per_update: Union[float, None] = None,
            fit_to_limit: bool = True,
            update_interval=None,
            use_market_maker_rate: bool = False):
        """
        Args:
            home_meter_profile: input profile defining the energy production/consumption of the
                Home Meter. It can be either a CSV file path, a dict with hourly data
                (Dict[int, float]) or a dict with arbitrary time data (Dict[str, float]).
            initial_selling_rate: Starting point for offers.
            final_selling_rate: Ending point for offers.
            energy_rate_decrease_per_update: Slope of the offers' change per update.
            initial_buying_rate: Starting point for bids.
            final_buying_rate: Ending point for bids.
            energy_rate_increase_per_update: Slope of the bids' change per update.
            fit_to_limit: If `True`, derive the bid/offer behavior from a linear fitted curve.
                - For offers: `energy_rate_decrease_per_update` is ignored and the rate will
                    decrease at each update_interval, starting at `initial_selling_rate` and ending
                    at `final_selling_rate`.
                - For bids: `energy_rate_increase_per_update` is ignored and the rate will
                    increase at each update_interval, starting at `initial_buying_rate` and ending
                    at `final_buying_rate`.
            update_interval: Interval in minutes after which the Home Meter will update its offers
                and bids.
            use_market_maker_rate: If set to True, the Home Meter will track its final buying and
                selling rate as per utility's trading rate.
        """
        super().__init__()  # TODO: what about args and kwargs?

        self.home_meter_profile = home_meter_profile
        self.profile = None  # Store the preprocessed data extracted from home_meter_profile

        self.initial_selling_rate = initial_selling_rate
        self.final_selling_rate = final_selling_rate
        self.energy_rate_decrease_per_update = energy_rate_decrease_per_update
        self.initial_buying_rate = initial_buying_rate
        self.final_buying_rate = final_buying_rate
        self.energy_rate_increase_per_update = energy_rate_increase_per_update
        self.fit_to_limit = fit_to_limit
        self.update_interval = self._convert_update_interval_to_duration(update_interval)
        self.use_market_maker_rate = use_market_maker_rate

        # validate_home_meter_device_energy()  # TODO (see pv.py and load_hours.py)
        # validate_home_meter_device_price()  # TODO (see pv.py)
        self.state = HomeMeterState()  # TODO: make hybrid with PV and Load states

        self._cycled_market = set()

        # Instances to update the Home Meter's bids and offers across all market slots
        self.bid_update = None
        self.offer_update = None
        self._init_price_update()

        self._calculate_active_markets()  # TODO refactor

    def _init_price_update(self):
        """Initialize the bid and offer updaters."""

        # TODO: rename variable
        self.bid_update = TemplateStrategyBidUpdater(
            initial_rate=self.initial_buying_rate,
            final_rate=self.final_buying_rate,
            fit_to_limit=self.fit_to_limit,
            energy_rate_change_per_update=self.energy_rate_increase_per_update,
            update_interval=self.update_interval,
            rate_limit_object=min)

        # TODO: rename variable
        self.offer_update = TemplateStrategyOfferUpdater(
            initial_rate=self.initial_selling_rate,
            final_rate=self.final_selling_rate,
            fit_to_limit=self.fit_to_limit,
            energy_rate_change_per_update=self.energy_rate_decrease_per_update,
            update_interval=self.update_interval,
            rate_limit_object=max)

    @property
    def active_markets(self):  # TODO: refactor
        return self._active_markets

    def _calculate_active_markets(self):  # TODO: refactor
        self._active_markets = [
            market for market in self.area.all_markets
            if self._is_market_active(market)
        ] if self.area else []

    def _is_market_active(self, market):  # TODO: refactor
        """
        Check if the market is active.

        To be defined as active, the market must be part of the total duration of the simulation,
        and it must come after the current market (if any).
        """
        return (
            market.in_sim_duration
            and (
                not self.area.current_market
                or market.time_slot >= self.area.current_market.time_slot))

    def event_activate(self, **kwargs):
        """Activate the device."""
        self._calculate_active_markets()
        self.event_activate_price()
        self.bid_update.update_and_populate_price_settings(self.area)
        self.event_activate_energy()
        # TODO: do the same operations for the offer prices!

    # TODO: refactor naming (it is not an event in the strict sense of the term)
    def event_activate_energy(self):
        """Run on ACTIVATE event."""
        # Read the power profile data and calculate the required energy for each slot
        self._event_activate_energy(self.home_meter_profile)  # TODO: change profile to read +/-
        self._simulation_start_timestamp = self.area.now
        self._update_energy_requirement_future_markets()
        del self.home_meter_profile  # TODO: Why?

    # TODO: refactor (return value, assign it later)
    def _event_activate_energy(self, home_meter_profile):
        """Read and preprocess the data of the power profile."""
        self.profile = read_arbitrary_profile(InputProfileTypes.POWER, home_meter_profile)

    @staticmethod
    def _convert_update_interval_to_duration(update_interval):
        if update_interval is None:
            return duration(minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL)
        elif isinstance(update_interval, int):
            return duration(minutes=update_interval)

    def event_market_cycle(self):
        super().event_market_cycle()
        self.bid_update.update_and_populate_price_settings(self.area)
        self._calculate_active_markets()
        self._update_energy_requirement_future_markets()
        self._set_alternative_pricing_scheme()
        self.update_state()

    def update_state(self):
        self.post_or_update_bid()
        if self.area.current_market:
            self._cycled_market.add(self.area.current_market.time_slot)
        self._delete_past_state()

    def post_or_update_bid(self):
        if ConstSettings.IAASettings.MARKET_TYPE == 1:
            return  # In a single-sided market, only offers are posted/updated

        for market in self.active_markets:
            if self.state.can_buy_more_energy(market.time_slot):
                bid_energy = self.state.calculate_energy_to_bid(market.time_slot)
                if self.is_eligible_for_balancing_market:
                    bid_energy -= self.state.get_desired_energy(market.time_slot) * \
                                  self.balancing_energy_ratio.demand
                try:
                    if not self.are_bids_posted(market.id):
                        self.post_first_bid(market, bid_energy)
                    else:
                        self.bid_update.reset(self)
                except MarketException:
                    pass

    def _delete_past_state(self):
        if constants.D3A_TEST_RUN is True or self.area.current_market is None:
            return

        self.state.delete_past_state_values(self.area.current_market.time_slot)
        self.bid_update.delete_past_state_values(self.area.current_market.time_slot)
        # TODO: do the same for the offers

    # TODO: is this needed?
    # TODO: include features for offers (PV)
    def _set_alternative_pricing_scheme(self):
        if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
            for market in self.area.all_markets:
                time_slot = market.time_slot
                final_rate = self.area.config.market_maker_rate[time_slot]
                self.bid_update.reassign_mixin_arguments(time_slot, initial_rate=0,
                                                         final_rate=final_rate)

    def _update_energy_requirement_future_markets(self) -> None:
        """Update required energy values for each market slot."""
        for market in self.area.all_markets:
            slot_time = market.time_slot
            if not self.profile:
                raise D3AException(
                    f"Home Meter {self.owner.name} tries to set its energy forecasted requirement "
                    "without a profile.")
            energy_kWh = find_object_of_same_weekday_and_time(self.profile, slot_time)
            self.state.set_desired_energy(energy_kWh * 1000, slot_time, overwrite=False)
            self.state.update_total_demanded_energy(slot_time)  # TODO: check if this must change

    # TODO: refactor naming (it is not an event in the strict sense of the term)
    def event_activate_price(self):
        """Configure all the rates for the device."""
        # If use_market_maker_rate is true, overwrite final_buying_rate to market maker rate
        if self.use_market_maker_rate:
            self._area_reconfigure_prices(
                final_buying_rate=get_market_maker_rate_from_config(
                    self.area.next_market, 0) + self.owner.get_path_to_root_fees(), validate=False)
            # TODO: do the same for initial_selling_rate

        # TODO: ?
        self._validate_rates(self.bid_update.initial_rate_profile_buffer,
                             self.bid_update.final_rate_profile_buffer,
                             self.bid_update.energy_rate_change_per_update_profile_buffer,
                             self.bid_update.fit_to_limit)

    def _area_reconfigure_prices(self, **kwargs):
        """Reconfigure the prices (rates) of the area.

        If custom profiles are provided in the `kwargs`, use them to replace the default ones
        provided by the UpdateFrequencyMixin.
        """
        # TODO: use offer_update as well (TemplateStrategyOfferUpdater)
        if key_in_dict_and_not_none(kwargs, "initial_buying_rate"):
            initial_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                  kwargs["initial_buying_rate"])
        else:
            initial_rate = self.bid_update.initial_rate_profile_buffer
        if key_in_dict_and_not_none(kwargs, "final_buying_rate"):
            final_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                kwargs["final_buying_rate"])
        else:
            final_rate = self.bid_update.final_rate_profile_buffer
        if key_in_dict_and_not_none(kwargs, "energy_rate_increase_per_update"):
            energy_rate_change_per_update = \
                read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                       kwargs["energy_rate_increase_per_update"])
        else:
            energy_rate_change_per_update = \
                self.bid_update.energy_rate_change_per_update_profile_buffer
        if key_in_dict_and_not_none(kwargs, "fit_to_limit"):
            fit_to_limit = kwargs["fit_to_limit"]
        else:
            fit_to_limit = self.bid_update.fit_to_limit
        if key_in_dict_and_not_none(kwargs, "update_interval"):
            if isinstance(kwargs["update_interval"], int):
                update_interval = duration(minutes=kwargs["update_interval"])
            else:
                update_interval = kwargs["update_interval"]
        else:
            update_interval = self.bid_update.update_interval

        if key_in_dict_and_not_none(kwargs, "use_market_maker_rate"):
            self.use_market_maker_rate = kwargs["use_market_maker_rate"]

        try:
            self._validate_rates(initial_rate, final_rate, energy_rate_change_per_update,
                                 fit_to_limit)
        except Exception as ex:
            log.exception(ex)
            return

        self.bid_update.set_parameters(
            initial_rate_profile_buffer=initial_rate,
            final_rate_profile_buffer=final_rate,
            energy_rate_change_per_update_profile_buffer=energy_rate_change_per_update,
            fit_to_limit=fit_to_limit,
            update_interval=update_interval
        )

    @staticmethod
    def _validate_rates(initial_rate, final_rate, energy_rate_change_per_update,
                        fit_to_limit):
        # all parameters have to be validated for each time slot here
        for time_slot in initial_rate.keys():
            rate_change = None if fit_to_limit else \
                find_object_of_same_weekday_and_time(energy_rate_change_per_update, time_slot)
            # TODO: this is not a load device. Create a new validation method for the HomeMeter
            validate_load_device_price(
                initial_buying_rate=initial_rate[time_slot],
                energy_rate_increase_per_update=rate_change,
                final_buying_rate=find_object_of_same_weekday_and_time(final_rate, time_slot),
                fit_to_limit=fit_to_limit)

    def event_tick(self):
        # Check if the device can buy energy in the future available market slots
        # TODO: check if it can offer as well (do not just immediately `continue`)
        for market in self.active_markets:
            if not self.state.can_buy_more_energy(market.time_slot):
                continue

            # Single-sided market (only offers are posted)
            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                self._one_sided_market_event_tick(market)
            # Double-sided markets (both offers and bids are posted)
            elif ConstSettings.IAASettings.MARKET_TYPE in [2, 3]:
                self._double_sided_market_event_tick(market)

        # Bids prices have been updated, so we increase the counter of the updates
        self.bid_update.increment_update_counter_all_markets(self)

    # TODO: split into two methods (with and without offer)
    def _one_sided_market_event_tick(self, market, offer=None):
        """
        Define the behavior of the device on TICK events in single-sided markets (react to offers).
        """
        try:
            if offer is None:
                if not market.offers:
                    return
                acceptable_offer = self._find_acceptable_offer(market)
            else:
                if offer.id not in market.offers:
                    return
                acceptable_offer = offer
            time_slot = market.time_slot
            # TODO: refactor this if statement (if the price is less than what we decided to spend)
            if acceptable_offer and \
                    round(acceptable_offer.energy_rate, DEFAULT_PRECISION) <= \
                    self.bid_update.final_rate[time_slot] + FLOATING_POINT_TOLERANCE:

                # TODO: put this on top or remove it
                if not self.state.can_buy_more_energy(time_slot):
                    return

                # If the device can still buy more energy
                energy_Wh = self.state.calculate_energy_to_accept(
                    acceptable_offer.energy * 1000.0, time_slot)
                self.accept_offer(market, acceptable_offer, energy=energy_Wh / 1000.0,
                                  buyer_origin=self.owner.name,
                                  buyer_origin_id=self.owner.uuid,
                                  buyer_id=self.owner.uuid)
                self.state.decrement_energy_requirement(energy_Wh, time_slot, self.owner.name)

        except MarketException:
            self.log.exception("An Error occurred while buying an offer")

    @staticmethod
    def _find_acceptable_offer(market):
        offers = market.most_affordable_offers
        return random.choice(offers)

    def _double_sided_market_event_tick(self, market):
        """
        Define the behavior of the device on TICK events in double-sided markets (post bids).
        """
        # Update the price of existing bids to reflect the new rates
        self.bid_update.update(market, self)
        # TODO: implement offers part

    def event_balancing_market_cycle(self):
        # TODO: implement
        pass

    def event_offer(self, *, market_id, offer):
        market = self.area.get_future_market_from_id(market_id)
        # TODO: do we really need self._cycled_market ?
        if market.time_slot not in self._cycled_market:
            return

        if self._can_buy_in_market(market) and self._offer_comes_from_different_seller(offer):
            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                self._one_sided_market_event_tick(market, offer)

    def _can_buy_in_market(self, market):
        return self._is_market_active(market) and self.state.can_buy_more_energy(market.time_slot)

    def _offer_comes_from_different_seller(self, offer):
        return offer.seller != self.owner.name and offer.seller != self.area.name
