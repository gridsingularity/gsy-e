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
from typing import Union
from collections import namedtuple
from enum import Enum
from pendulum import duration

from d3a import limit_float_precision
from d3a.d3a_core.exceptions import MarketException
from d3a.d3a_core.util import area_name_from_area_or_iaa_name, generate_market_slot_list
from d3a.models.state import StorageState, ESSEnergyOrigin, EnergyOrigin
from d3a.models.strategy import BidEnabledStrategy
from d3a_interface.constants_limits import ConstSettings
from d3a_interface.device_validator import validate_storage_device
from d3a.models.strategy.update_frequency import UpdateFrequencyMixin
from d3a.models.read_user_profile import read_arbitrary_profile, InputProfileTypes
from d3a.d3a_core.device_registry import DeviceRegistry

BalancingRatio = namedtuple('BalancingRatio', ('demand', 'supply'))

StorageSettings = ConstSettings.StorageSettings
GeneralSettings = ConstSettings.GeneralSettings
BalancingSettings = ConstSettings.BalancingSettings


class StorageStrategy(BidEnabledStrategy):
    parameters = ('initial_soc', 'min_allowed_soc', 'battery_capacity_kWh',
                  'max_abs_battery_power_kW', 'cap_price_strategy', 'initial_selling_rate',
                  'final_selling_rate', 'initial_buying_rate', 'final_buying_rate', 'fit_to_limit',
                  'update_interval', 'initial_energy_origin', 'balancing_energy_ratio')

    def __init__(self, initial_soc: float = StorageSettings.MIN_ALLOWED_SOC,
                 min_allowed_soc=StorageSettings.MIN_ALLOWED_SOC,
                 battery_capacity_kWh: float = StorageSettings.CAPACITY,
                 max_abs_battery_power_kW: float = StorageSettings.MAX_ABS_POWER,
                 cap_price_strategy: bool = False,
                 initial_selling_rate: Union[float, dict] =
                 StorageSettings.SELLING_RATE_RANGE.initial,
                 final_selling_rate: Union[float, dict] =
                 StorageSettings.SELLING_RATE_RANGE.final,
                 initial_buying_rate: Union[float, dict] =
                 StorageSettings.BUYING_RATE_RANGE.initial,
                 final_buying_rate: Union[float, dict] =
                 StorageSettings.BUYING_RATE_RANGE.final,
                 fit_to_limit=True, energy_rate_increase_per_update=1,
                 energy_rate_decrease_per_update=1,
                 update_interval=duration(
                     minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL),
                 initial_energy_origin: Enum = ESSEnergyOrigin.EXTERNAL,
                 balancing_energy_ratio: tuple = (BalancingSettings.OFFER_DEMAND_RATIO,
                                                  BalancingSettings.OFFER_SUPPLY_RATIO)):

        if min_allowed_soc is None:
            min_allowed_soc = StorageSettings.MIN_ALLOWED_SOC

        validate_storage_device(initial_soc=initial_soc, min_allowed_soc=min_allowed_soc,
                                battery_capacity_kWh=battery_capacity_kWh,
                                max_abs_battery_power_kW=max_abs_battery_power_kW)

        if isinstance(update_interval, int):
            update_interval = duration(minutes=update_interval)

        BidEnabledStrategy.__init__(self)

        self.offer_update = \
            UpdateFrequencyMixin(initial_rate=initial_selling_rate,
                                 final_rate=final_selling_rate,
                                 fit_to_limit=fit_to_limit,
                                 energy_rate_change_per_update=energy_rate_decrease_per_update,
                                 update_interval=update_interval)
        for time_slot in generate_market_slot_list():
            validate_storage_device(
                initial_selling_rate=self.offer_update.initial_rate[time_slot],
                final_selling_rate=self.offer_update.final_rate[time_slot])
        self.bid_update = \
            UpdateFrequencyMixin(
                initial_rate=initial_buying_rate,
                final_rate=final_buying_rate,
                fit_to_limit=fit_to_limit,
                energy_rate_change_per_update=-1 * energy_rate_increase_per_update,
                update_interval=update_interval,
                rate_limit_object=min
            )
        for time_slot in generate_market_slot_list():
            validate_storage_device(
                initial_buying_rate=self.bid_update.initial_rate[time_slot],
                final_buying_rate=self.bid_update.final_rate[time_slot])
        self.state = \
            StorageState(initial_soc=initial_soc,
                         initial_energy_origin=initial_energy_origin,
                         capacity=battery_capacity_kWh,
                         max_abs_battery_power_kW=max_abs_battery_power_kW,
                         loss_per_hour=0.0,
                         min_allowed_soc=min_allowed_soc)
        self.cap_price_strategy = cap_price_strategy
        self.balancing_energy_ratio = BalancingRatio(*balancing_energy_ratio)

    def _update_rate_parameters(self, initial_selling_rate, final_selling_rate,
                                initial_buying_rate, final_buying_rate,
                                energy_rate_change_per_update):
        if initial_selling_rate is not None:
            self.offer_update.initial_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                                    initial_selling_rate)
        if final_selling_rate is not None:
            self.offer_update.final_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                                  final_selling_rate)
        if initial_buying_rate is not None:
            self.bid_update.initial_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                                  initial_buying_rate)
        if final_buying_rate is not None:
            self.bid_update.final_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                                final_buying_rate)
        if energy_rate_change_per_update is not None:
            self.offer_update.energy_rate_change_per_update = \
                read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                       energy_rate_change_per_update)
            self.bid_update.energy_rate_change_per_update = \
                read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                       energy_rate_change_per_update)

    def area_reconfigure_event(self, cap_price_strategy=None,
                               initial_selling_rate=None, final_selling_rate=None,
                               initial_buying_rate=None, final_buying_rate=None,
                               fit_to_limit=None, update_interval=None,
                               energy_rate_change_per_update=None):

        validate_storage_device(initial_selling_rate=initial_selling_rate,
                                final_selling_rate=final_selling_rate,
                                initial_buying_rate=initial_buying_rate,
                                final_buying_rate=final_buying_rate,
                                energy_rate_change_per_update=energy_rate_change_per_update)
        if cap_price_strategy is not None:
            self.cap_price_strategy = cap_price_strategy
        self._update_rate_parameters(initial_selling_rate, final_selling_rate,
                                     initial_buying_rate, final_buying_rate,
                                     energy_rate_change_per_update)
        self.offer_update.update_on_activate()
        self.bid_update.update_on_activate()

    def event_on_disabled_area(self):
        self.state.calculate_soc_for_time_slot(self.area.next_market.time_slot)

    def event_activate(self):
        self.state.set_battery_energy_per_slot(self.area.config.slot_length)
        self.offer_update.update_on_activate()
        self.bid_update.update_on_activate()
        self._set_alternative_pricing_scheme()

    def _set_alternative_pricing_scheme(self):
        if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
            if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 1:
                for time_slot in generate_market_slot_list():
                    self.bid_update.reassign_mixin_arguments(time_slot, initial_rate=0,
                                                             final_rate=0)
                    self.offer_update.reassign_mixin_arguments(time_slot, initial_rate=0,
                                                               final_rate=0)
            elif ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 2:
                for time_slot in generate_market_slot_list():
                    rate = \
                        self.area.config.market_maker_rate[time_slot] * \
                        ConstSettings.IAASettings.AlternativePricing.FEED_IN_TARIFF_PERCENTAGE / \
                        100
                    self.bid_update.reassign_mixin_arguments(time_slot, initial_rate=0,
                                                             final_rate=rate)
                    self.offer_update.reassign_mixin_arguments(time_slot,
                                                               initial_rate=rate,
                                                               final_rate=rate)
            elif ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 3:
                for time_slot in generate_market_slot_list():
                    rate = self.area.config.market_maker_rate[time_slot]
                    self.bid_update.reassign_mixin_arguments(time_slot, initial_rate=0,
                                                             final_rate=rate)
                    self.offer_update.reassign_mixin_arguments(time_slot,
                                                               initial_rate=rate,
                                                               final_rate=rate)
            else:
                raise MarketException

    @staticmethod
    def _validate_constructor_arguments(initial_soc=None, min_allowed_soc=None,
                                        battery_capacity_kWh=None, max_abs_battery_power_kW=None,
                                        initial_selling_rate=None, final_selling_rate=None,
                                        initial_buying_rate=None, final_buying_rate=None,
                                        energy_rate_change_per_update=None):
        if battery_capacity_kWh is not None and battery_capacity_kWh < 0:
            raise ValueError("Battery capacity should be a positive integer")
        if max_abs_battery_power_kW is not None and max_abs_battery_power_kW < 0:
            raise ValueError("Battery Power rating must be a positive integer.")
        if initial_soc is not None and 0 < initial_soc > 100:
            raise ValueError("initial SOC must be in between 0-100 %")
        if min_allowed_soc is not None and 0 < min_allowed_soc > 100:
            raise ValueError("initial SOC must be in between 0-100 %")
        if initial_soc is not None and min_allowed_soc is not None and \
                initial_soc < min_allowed_soc:
            raise ValueError("Initial charge must be more than the minimum allowed soc.")
        if initial_selling_rate is not None and initial_selling_rate < 0:
            raise ValueError("Initial selling rate must be greater equal 0.")
        if final_selling_rate is not None:
            if type(final_selling_rate) is float and final_selling_rate < 0:
                raise ValueError("Final selling rate must be greater equal 0.")
            elif type(final_selling_rate) is dict and \
                    any(rate < 0 for _, rate in final_selling_rate.items()):
                raise ValueError("Final selling rate must be greater equal 0.")
        if initial_selling_rate is not None and final_selling_rate is not None:
            initial_selling_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                          initial_selling_rate)
            final_selling_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                        final_selling_rate)
            if any(initial_selling_rate[hour] < final_selling_rate[hour]
                   for hour, _ in initial_selling_rate.items()):
                raise ValueError("Initial selling rate must be greater than final selling rate.")
        if initial_buying_rate is not None and initial_buying_rate < 0:
            raise ValueError("Initial buying rate must be greater equal 0.")
        if final_buying_rate is not None:
            final_buying_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                       final_buying_rate)
            if any(rate < 0 for _, rate in final_buying_rate.items()):
                raise ValueError("Final buying rate must be greater equal 0.")
        if initial_buying_rate is not None and final_buying_rate is not None:
            initial_buying_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                         initial_buying_rate)
            final_buying_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                       final_buying_rate)
            if any(initial_buying_rate[hour] > final_buying_rate[hour]
                   for hour, _ in initial_buying_rate.items()):
                raise ValueError("Initial buying rate must be less than final buying rate.")
        if final_selling_rate is not None and final_buying_rate is not None:
            final_selling_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                        final_selling_rate)
            final_buying_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                       final_buying_rate)
            if any(final_buying_rate[hour] >= final_selling_rate[hour]
                   for hour, _ in final_selling_rate.items()):
                raise ValueError("final_buying_rate should be higher than final_selling_rate.")
        if energy_rate_change_per_update is not None and energy_rate_change_per_update < 0:
            raise ValueError("energy_rate_change_per_update should be a non-negative value.")

    def event_tick(self):
        self.state.clamp_energy_to_buy_kWh([ma.time_slot for ma in self.area.all_markets])
        for market in self.area.all_markets:
            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                if self.bid_update.get_price_update_point(self, market.time_slot):
                    self.buy_energy(market)
            elif ConstSettings.IAASettings.MARKET_TYPE == 2 or \
                    ConstSettings.IAASettings.MARKET_TYPE == 3:

                if self.are_bids_posted(market.id):
                    self.bid_update.update_posted_bids_over_ticks(market, self)
                else:
                    energy_kWh = self.state.energy_to_buy_dict[market.time_slot]
                    if energy_kWh > 0:
                        first_bid = self.post_first_bid(market, energy_kWh * 1000.0)
                        if first_bid is not None:
                            self.state.offered_buy_kWh[market.time_slot] += first_bid.energy

            self.state.tick(self.area, market.time_slot)
            if self.cap_price_strategy is False:
                self.offer_update.update_offer(self)

    def event_trade(self, *, market_id, trade):
        market = self.area.get_future_market_from_id(market_id)
        super().event_trade(market_id=market_id, trade=trade)
        if trade.buyer == self.owner.name:
            self._track_energy_bought_type(trade)
        if trade.offer.seller == self.owner.name:
            self._track_energy_sell_type(trade)
            self.state.pledged_sell_kWh[market.time_slot] += trade.offer.energy
            self.state.offered_sell_kWh[market.time_slot] -= trade.offer.energy

    def _is_local(self, trade):
        for child in self.area.children:
            if child.name == trade.seller:
                return True

    # ESS Energy being utilized based on FIRST-IN FIRST-OUT mechanism
    def _track_energy_sell_type(self, trade):
        energy = trade.offer.energy
        while limit_float_precision(energy) > 0:
            first_in_energy_with_origin = self.state.get_used_storage_share[0]
            if energy >= first_in_energy_with_origin.value:
                energy -= first_in_energy_with_origin.value
                self.state.get_used_storage_share.pop(0)
            elif energy < first_in_energy_with_origin.value:
                residual = first_in_energy_with_origin.value - energy
                self.state._used_storage_share[0] = \
                    EnergyOrigin(first_in_energy_with_origin.origin, residual)
                energy = 0

    def _track_energy_bought_type(self, trade):
        if area_name_from_area_or_iaa_name(trade.seller) == self.area.name:
            self.state.update_used_storage_share(trade.offer.energy, ESSEnergyOrigin.EXTERNAL)
        elif self._is_local(trade):
            self.state.update_used_storage_share(trade.offer.energy, ESSEnergyOrigin.LOCAL)
        else:
            self.state.update_used_storage_share(trade.offer.energy, ESSEnergyOrigin.UNKNOWN)

    def event_bid_traded(self, *, market_id, bid_trade):
        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)
        market = self.area.get_future_market_from_id(market_id)

        if bid_trade.offer.buyer == self.owner.name:
            self._track_energy_bought_type(bid_trade)
            self.state.pledged_buy_kWh[market.time_slot] += bid_trade.offer.energy
            self.state.offered_buy_kWh[market.time_slot] -= bid_trade.offer.energy

    def event_market_cycle(self):
        super().event_market_cycle()
        self.offer_update.update_market_cycle_offers(self)
        for market in self.area.all_markets[:-1]:
            self.bid_update.update_counter[market.time_slot] = 0
        current_market = self.area.next_market
        past_market = self.area.last_past_market

        self.state.market_cycle(
            past_market.time_slot if past_market else current_market.time_slot,
            current_market.time_slot
        )

        if self.state.used_storage > 0:
            self.sell_energy()

        if ConstSettings.IAASettings.MARKET_TYPE == 2 or \
           ConstSettings.IAASettings.MARKET_TYPE == 3:
            self.state.clamp_energy_to_buy_kWh([current_market.time_slot])
            self.bid_update.update_market_cycle_bids(self)
            energy_kWh = self.state.energy_to_buy_dict[current_market.time_slot]
            if energy_kWh > 0:
                self.post_first_bid(current_market, energy_kWh * 1000.0)
                self.state.offered_buy_kWh[current_market.time_slot] += energy_kWh

    def event_balancing_market_cycle(self):
        if not self.is_eligible_for_balancing_market:
            return

        current_market = self.area.next_market
        free_storage = self.state.free_storage(current_market.time_slot)
        if free_storage > 0:
            charge_energy = self.balancing_energy_ratio.demand * free_storage
            charge_price = DeviceRegistry.REGISTRY[self.owner.name][0] * charge_energy
            if charge_energy != 0 and charge_price != 0:
                # committing to start charging when required
                self.area.get_balancing_market(self.area.now).balancing_offer(charge_price,
                                                                              -charge_energy,
                                                                              self.owner.name)
        if self.state.used_storage > 0:
            discharge_energy = self.balancing_energy_ratio.supply * self.state.used_storage
            discharge_price = DeviceRegistry.REGISTRY[self.owner.name][1] * discharge_energy
            # committing to start discharging when required
            if discharge_energy != 0 and discharge_price != 0:
                self.area.get_balancing_market(self.area.now).balancing_offer(discharge_price,
                                                                              discharge_energy,
                                                                              self.owner.name)

    def buy_energy(self, market):
        max_affordable_offer_rate = min(self.bid_update.get_updated_rate(market.time_slot),
                                        self.bid_update.final_rate[market.time_slot])
        for offer in market.sorted_offers:
            if offer.seller == self.owner.name:
                # Don't buy our own offer
                continue

            alt_pricing_settings = ConstSettings.IAASettings.AlternativePricing
            if offer.seller == alt_pricing_settings.ALT_PRICING_MARKET_MAKER_NAME \
                    and alt_pricing_settings.PRICING_SCHEME != 0:
                # don't buy from IAA if alternative pricing scheme is activated
                continue
            # Check if storage has free capacity and if the price is cheap enough
            if self.state.free_storage(market.time_slot) > 0.0 \
                    and (offer.price / offer.energy) <= max_affordable_offer_rate:
                try:
                    max_energy = min(offer.energy, self.state.energy_to_buy_dict[market.time_slot])
                    if not self.state.has_battery_reached_max_power(-max_energy, market.time_slot):
                        self.accept_offer(market, offer, energy=max_energy,
                                          buyer_origin=self.owner.name)
                        self.state.pledged_buy_kWh[market.time_slot] += max_energy
                        return True

                except MarketException:
                    # Offer already gone etc., try next one.
                    return False
            else:
                return False

    def sell_energy(self):
        markets_to_sell = self.select_market_to_sell()
        energy_sell_dict = self.state.clamp_energy_to_sell_kWh(
            [ma.time_slot for ma in markets_to_sell])
        for market in markets_to_sell:
            selling_rate = self.calculate_selling_rate(market)
            energy = energy_sell_dict[market.time_slot]
            if not self.state.has_battery_reached_max_power(energy, market.time_slot):
                if energy > 0.0:
                    offer = market.offer(
                        energy * selling_rate,
                        energy,
                        self.owner.name,
                        original_offer_price=energy * selling_rate,
                        seller_origin=self.owner.name
                    )
                    self.offers.post(offer, market.id)
                    self.state.offered_sell_kWh[market.time_slot] += offer.energy

    def select_market_to_sell(self):
        if StorageSettings.SELL_ON_MOST_EXPENSIVE_MARKET:
            # Sell on the most expensive market
            try:
                max_rate = 0.0
                most_expensive_market = self.area.all_markets[0]
                for market in self.area.markets.values():
                    if len(market.sorted_offers) > 0 and \
                       market.sorted_offers[0].price / market.sorted_offers[0].energy > max_rate:
                        max_rate = market.sorted_offers[0].price / market.sorted_offers[0].energy
                        most_expensive_market = market
            except IndexError:
                try:
                    most_expensive_market = self.area.current_market
                except StopIteration:
                    return
            return [most_expensive_market]
        else:
            return self.area.all_markets

    def calculate_selling_rate(self, market):
        if self.cap_price_strategy is True:
            return self.capacity_dependant_sell_rate(market)
        else:
            return self.offer_update.initial_rate[market.time_slot]

    def capacity_dependant_sell_rate(self, market):
        if self.state.charge_history[market.time_slot] is '-':
            soc = self.state.used_storage / self.state.capacity
        else:
            soc = self.state.charge_history[market.time_slot] / 100.0
        max_selling_rate = self.offer_update.initial_rate[market.time_slot]
        min_selling_rate = self.offer_update.final_rate[market.time_slot]
        if max_selling_rate < min_selling_rate:
            return min_selling_rate
        else:
            return max_selling_rate - (max_selling_rate - min_selling_rate) * soc
