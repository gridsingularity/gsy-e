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
from enum import Enum
from cached_property import cached_property
from typing import Dict  # noqa
from pendulum import Time  # noqa

from d3a.d3a_core.exceptions import MarketException
from d3a.models.const import ConstSettings


class InitialRateOptions(Enum):
    HISTORICAL_AVG_RATE = 1
    MARKET_MAKER_RATE = 2
    CUSTOM_RATE = 3


class RateDecreaseOption(Enum):
    PERCENTAGE_BASED_ENERGY_RATE_DECREASE = 1
    CONST_ENERGY_RATE_DECREASE_PER_UPDATE = 2


class BidUpdateFrequencyMixin:
    def __init__(self,
                 initial_rate_profile,
                 final_rate_profile):
        self._initial_rate_profile = initial_rate_profile
        self._final_rate_profile = final_rate_profile
        self._increase_rate_timepoint_s = {}

    @cached_property
    def _increase_frequency_s(self):
        return self.area.config.tick_length.seconds * \
               ConstSettings.GeneralSettings.MAX_OFFER_TRAVERSAL_LENGTH

    def post_first_bid(self, market, energy_Wh):
        # TODO: It will be safe to remove this check once we remove the event_market_cycle being
        # called twice, but still it is nice to have it here as a precaution. In general, there
        # should be only bid from a device to a market at all times, which will be replaced if
        # it needs to be updated. If this check is not there, the market cycle event will post
        # one bid twice, which actually happens on the very first market slot cycle.
        if not all(bid.buyer != self.owner.name for bid in market.bids.values()):
            self.owner.log.warning(f"There is already another bid posted on the market, therefore"
                                   f" do not repost another first bid.")
            return None
        return self.post_bid(
            market,
            energy_Wh * self._initial_rate_profile[market.time_slot] / 1000.0,
            energy_Wh / 1000.0
        )

    def update_market_cycle_bids(self, final_rate=None):
        if final_rate is not None:
            self._final_rate = final_rate
        current_tick_number = self.area.current_tick % self.area.config.ticks_per_slot

        for market in self.area.all_markets:
            self._increase_rate_timepoint_s[market.time_slot] = self._increase_frequency_s
        # decrease energy rate for each market again, except for the newly created one
        for market in self.area.all_markets[:-1]:
            self._update_posted_bids(market, current_tick_number)

    def _update_posted_bids(self, market, current_tick_number):
        existing_bids = list(self.get_posted_bids(market))
        for bid in existing_bids:
            if bid.id in market.bids.keys():
                bid = market.bids[bid.id]
            market.delete_bid(bid.id)

            self.remove_bid_from_pending(bid.id, market)
            rate = self._get_current_energy_rate(current_tick_number, market)
            self.post_bid(market,
                          bid.energy * rate,
                          bid.energy)

    def update_posted_bids_over_ticks(self, market):
        # Decrease the selling price over the ticks in a slot
        current_tick_number = self.area.current_tick % self.area.config.ticks_per_slot
        elapsed_seconds = current_tick_number * self.area.config.tick_length.seconds
        if elapsed_seconds > self._increase_rate_timepoint_s[market.time_slot]:
            self._increase_rate_timepoint_s[market.time_slot] += self._increase_frequency_s
            self._update_posted_bids(market, current_tick_number)

    def _get_current_energy_rate(self, current_tick, market):
        total_ticks = (self.area.config.ticks_per_slot -
                       ConstSettings.GeneralSettings.MAX_OFFER_TRAVERSAL_LENGTH)
        percentage_of_rate = max(min(current_tick / total_ticks, 1.0), 0.0)
        rate_range = self._final_rate_profile[market.time_slot] - \
            self._initial_rate_profile[market.time_slot]
        return rate_range * percentage_of_rate + self._initial_rate_profile[market.time_slot]


class OfferUpdateFrequencyMixin:

    def __init__(self,
                 initial_rate_option,
                 initial_selling_rate,
                 energy_rate_decrease_option,
                 energy_rate_decrease_per_update,
                 ):
        self.assign_offermixin_arguments(initial_rate_option, energy_rate_decrease_option,
                                         energy_rate_decrease_per_update)
        self._decrease_price_timepoint_s = {}  # type: Dict[Time, float]
        self._decrease_price_every_nr_s = 0
        self.initial_selling_rate = initial_selling_rate

    def assign_offermixin_arguments(self, initial_rate_option, energy_rate_decrease_option,
                                    energy_rate_decrease_per_update):
        if initial_rate_option is not None:
            self.initial_rate_option = InitialRateOptions(initial_rate_option)
        if energy_rate_decrease_option is not None:
            self.energy_rate_decrease_option = RateDecreaseOption(energy_rate_decrease_option)
        if energy_rate_decrease_per_update is not None:
            if energy_rate_decrease_per_update < 0:
                raise ValueError("Energy rate decrease per update should be a positive value.")
            self.energy_rate_decrease_per_update = energy_rate_decrease_per_update

    def update_on_activate(self):
        # This update of _decrease_price_every_nr_s can only be done after activation as
        # MAX_OFFER_TRAVERSAL_LENGTH is not known at construction
        self._decrease_price_every_nr_s = \
            (self.area.config.tick_length.seconds *
             ConstSettings.GeneralSettings.MAX_OFFER_TRAVERSAL_LENGTH + 1)

    def calculate_initial_sell_rate(self, current_time_h):
        if self.initial_rate_option is InitialRateOptions.HISTORICAL_AVG_RATE:
            if self.area.historical_avg_rate == 0:
                return self.area.config.market_maker_rate[current_time_h]
            else:
                return self.area.historical_avg_rate
        elif self.initial_rate_option is InitialRateOptions.MARKET_MAKER_RATE:
            return self.area.config.market_maker_rate[current_time_h]
        elif self.initial_rate_option is InitialRateOptions.CUSTOM_RATE:
            return self.initial_selling_rate
        else:
            raise ValueError("Initial rate option should be one of the InitialRateOptions.")

    def decrease_energy_price_over_ticks(self, market):
        if market.time_slot not in self._decrease_price_timepoint_s:
            self._decrease_price_timepoint_s[market.time_slot] = 0
        # Decrease the selling price over the ticks in a slot
        current_tick_number = self.area.current_tick % self.area.config.ticks_per_slot
        elapsed_seconds = current_tick_number * self.area.config.tick_length.seconds
        if elapsed_seconds > self._decrease_price_timepoint_s[market.time_slot]:
            self._decrease_price_timepoint_s[market.time_slot] += self._decrease_price_every_nr_s

            self._decrease_offer_price(market,
                                       self._calculate_price_decrease_rate(market))

    def _decrease_offer_price(self, market, decrease_rate_per_tick):
        if market not in self.offers.open.values():
            return

        for offer, iterated_market in self.offers.open.items():
            if iterated_market != market:
                continue
            try:
                iterated_market.delete_offer(offer.id)
                new_offer = iterated_market.offer(
                    round(offer.price - (offer.energy *
                          decrease_rate_per_tick), 10),
                    offer.energy,
                    self.owner.name
                )
                if (new_offer.price/new_offer.energy) < self.final_selling_rate:
                    new_offer.price = self.final_selling_rate * new_offer.energy
                self.offers.replace(offer, new_offer, iterated_market)
            except MarketException:
                continue

    def _calculate_price_decrease_rate(self, market):
        if self.energy_rate_decrease_option is \
                RateDecreaseOption.PERCENTAGE_BASED_ENERGY_RATE_DECREASE:
            price_dec_per_slot = self.calculate_initial_sell_rate(market.time_slot) * \
                                 (1 - self.risk/ConstSettings.GeneralSettings.MAX_RISK)
            price_updates_per_slot = int(self.area.config.slot_length.seconds
                                         / self._decrease_price_every_nr_s)
            price_dec_per_update = price_dec_per_slot / price_updates_per_slot
            return price_dec_per_update
        elif self.energy_rate_decrease_option is \
                RateDecreaseOption.CONST_ENERGY_RATE_DECREASE_PER_UPDATE:
            return self.energy_rate_decrease_per_update

    def update_market_cycle_offers(self, final_selling_rate):
        self.final_selling_rate = final_selling_rate
        # increase energy rate for each market again, except for the newly created one
        for market in self.area.all_markets:
            self._decrease_price_timepoint_s[market.time_slot] = self._decrease_price_every_nr_s
        for market in self.area.all_markets[:-1]:
            self.reset_price_on_market_cycle(market)

    def reset_price_on_market_cycle(self, market):
        if market not in self.offers.open.values():
            return

        for offer, iterated_market in self.offers.open.items():
            if iterated_market != market:
                continue
            try:
                iterated_market.delete_offer(offer.id)

                new_offer = iterated_market.offer(
                    offer.energy * self.calculate_initial_sell_rate(iterated_market.time_slot),
                    offer.energy,
                    self.owner.name
                )
                self.offers.replace(offer, new_offer, iterated_market)
            except MarketException:
                continue

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
