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

from d3a.d3a_core.exceptions import MarketException
from d3a.models.state import StorageState
from d3a.models.strategy import BidEnabledStrategy
from d3a.models.const import ConstSettings
from d3a.models.strategy.update_frequency import OfferUpdateFrequencyMixin, \
    BidUpdateFrequencyMixin
from d3a.models.read_user_profile import read_arbitrary_profile
from d3a.models.read_user_profile import InputProfileTypes
from d3a.d3a_core.device_registry import DeviceRegistry

BalancingRatio = namedtuple('BalancingRatio', ('demand', 'supply'))
BreakEven = namedtuple('BreakEven', ('buy', 'sell'))

StorageSettings = ConstSettings.StorageSettings
GeneralSettings = ConstSettings.GeneralSettings
BalancingSettings = ConstSettings.BalancingSettings


class StorageStrategy(BidEnabledStrategy, OfferUpdateFrequencyMixin, BidUpdateFrequencyMixin):
    parameters = ('risk', 'initial_capacity_kWh', 'initial_soc', 'initial_rate_option',
                  'energy_rate_decrease_option', 'energy_rate_decrease_per_update',
                  'battery_capacity_kWh', 'max_abs_battery_power_kW', 'break_even',
                  'initial_selling_rate')

    def __init__(self, risk: int=GeneralSettings.DEFAULT_RISK,
                 initial_capacity_kWh: float=None,
                 initial_soc: float=None,
                 initial_rate_option: int=StorageSettings.INITIAL_RATE_OPTION,
                 initial_selling_rate:
                 float=StorageSettings.MAX_SELLING_RATE,
                 energy_rate_decrease_option: int=StorageSettings.RATE_DECREASE_OPTION,
                 energy_rate_decrease_per_update:
                 float=GeneralSettings.ENERGY_RATE_DECREASE_PER_UPDATE,  # NOQA
                 battery_capacity_kWh: float=StorageSettings.CAPACITY,
                 max_abs_battery_power_kW: float=StorageSettings.MAX_ABS_POWER,
                 break_even: Union[tuple, dict]=(StorageSettings.BREAK_EVEN_BUY,
                             StorageSettings.BREAK_EVEN_SELL),
                 balancing_energy_ratio: tuple=(BalancingSettings.OFFER_DEMAND_RATIO,
                                                BalancingSettings.OFFER_SUPPLY_RATIO),
                 cap_price_strategy: bool=False,
                 min_allowed_soc=None):

        if min_allowed_soc is None:
            min_allowed_soc = StorageSettings.MIN_ALLOWED_SOC

        self.break_even = self._validate_break_even_points(break_even)
        self._validate_constructor_arguments(risk, initial_capacity_kWh,
                                             initial_soc, battery_capacity_kWh,
                                             min_allowed_soc, initial_selling_rate)
        BidEnabledStrategy.__init__(self)

        self.final_selling_rate = next(iter(self.break_even.values())).sell
        OfferUpdateFrequencyMixin.__init__(self, initial_rate_option,
                                           initial_selling_rate,
                                           energy_rate_decrease_option,
                                           energy_rate_decrease_per_update)

        # Normalize min/max buying rate profiles before passing to the bid mixin
        self.min_buying_rate_profile = read_arbitrary_profile(
            InputProfileTypes.IDENTITY,
            StorageSettings.MIN_BUYING_RATE
        )
        self.max_buying_rate_profile = {k: v.buy for k, v in self.break_even.items()}
        BidUpdateFrequencyMixin.__init__(self,
                                         initial_rate_profile=self.min_buying_rate_profile,
                                         final_rate_profile=self.max_buying_rate_profile)

        self.risk = risk
        self.state = StorageState(initial_capacity_kWh=initial_capacity_kWh,
                                  initial_soc=initial_soc,
                                  capacity=battery_capacity_kWh,
                                  max_abs_battery_power_kW=max_abs_battery_power_kW,
                                  loss_per_hour=0.0,
                                  strategy=self,
                                  min_allowed_soc=min_allowed_soc)
        self.cap_price_strategy = cap_price_strategy
        self.balancing_energy_ratio = BalancingRatio(*balancing_energy_ratio)

    def area_reconfigure_event(self, risk=None, initial_rate_option=None,
                               energy_rate_decrease_option=None,
                               energy_rate_decrease_per_update=None,
                               battery_capacity_kWh=None,
                               max_abs_battery_power_kW=None, break_even=None,
                               min_allowed_soc=None):
        if break_even is not None:
            self.break_even = self._validate_break_even_points(break_even)
            self.initial_selling_rate = list(break_even.values())[0][1]
            self.max_buying_rate_profile = {k: v[1] for k, v in break_even.items()}

        self._validate_constructor_arguments(risk, None, None, battery_capacity_kWh,
                                             min_allowed_soc, self.initial_selling_rate)
        self.assign_offermixin_arguments(initial_rate_option, energy_rate_decrease_option,
                                         energy_rate_decrease_per_update)
        if battery_capacity_kWh is not None:
            self.state.capacity = battery_capacity_kWh
        if max_abs_battery_power_kW is not None:
            self.state.max_abs_battery_power_kW = max_abs_battery_power_kW
        if risk is not None:
            self.risk = risk
        if min_allowed_soc is not None:
            self.state.min_allowed_soc = min_allowed_soc

    def event_on_disabled_area(self):
        self.state.calculate_soc_for_time_slot(self.area.next_market.time_slot)

    def event_activate(self):

        self._set_be_alternative_pricing()
        self.update_market_cycle_offers(self.break_even[self.area.now][1])
        self.state.set_battery_energy_per_slot(self.area.config.slot_length)
        self.update_on_activate()

    def _set_be_alternative_pricing(self):
        if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
            self.assign_offermixin_arguments(3, 2, 0)
            if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 1:
                self.break_even = {k: (0, 0) for k in self.break_even.keys()}
            elif ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 2:
                for time_slot in self.break_even.keys():
                    rate = self.area.config.market_maker_rate[time_slot] * \
                           ConstSettings.IAASettings.AlternativePricing.FEED_IN_TARIFF_PERCENTAGE\
                           / 100
                    self.break_even[time_slot] = (rate, rate)
            elif ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 3:
                for time_slot in self.break_even.keys():
                    rate = self.area.config.market_maker_rate[time_slot]
                    self.break_even[time_slot] = (rate, rate)
            else:
                raise MarketException

    @staticmethod
    def _validate_break_even_points(break_even):
        if type(break_even) not in [tuple, list, dict]:
            raise ValueError("Break even points have to be a tuple, list or dict.")

        if type(break_even) is list:
            break_even = tuple(break_even)
        if type(break_even) is tuple:
            break_even = BreakEven(*break_even)
        elif type(break_even) is dict:
            break_even = {k: BreakEven(*v) for k, v in break_even.items()}

        break_even = read_arbitrary_profile(InputProfileTypes.IDENTITY, break_even)
        if any(be.sell < be.buy for _, be in break_even.items()):
            raise ValueError("Break even point for sell energy is lower than buy energy.")
        if any(break_even_point.buy < 0 or break_even_point.sell < 0
               for _, break_even_point in break_even.items()):
            raise ValueError("Break even point should be positive energy rate values.")
        return break_even

    @staticmethod
    def _validate_constructor_arguments(risk, initial_capacity_kWh, initial_soc,
                                        battery_capacity_kWh, min_allowed_soc,
                                        initial_selling_rate):
        if battery_capacity_kWh and battery_capacity_kWh < 0:
            raise ValueError("Battery capacity should be a positive integer")
        if initial_soc and not min_allowed_soc <= initial_soc <= 100:
            raise ValueError("Initial charge is a percentage value, should be between "
                             "MIN_ALLOWED_SOC and 100.")
        if risk and not 0 <= risk <= 100:
            raise ValueError("Risk is a percentage value, should be between 0 and 100.")
        if initial_capacity_kWh and battery_capacity_kWh and min_allowed_soc and \
           not min_allowed_soc * battery_capacity_kWh <= \
           initial_capacity_kWh <= battery_capacity_kWh:
            raise ValueError(f"Initial capacity should be between min_allowed_capacity and "
                             "battery_capacity_kWh parameter.")
        if initial_selling_rate < 0:
            raise ValueError("Initial selling rate must be greater equal 0.")

    def event_tick(self, *, area):
        self.state.clamp_energy_to_buy_kWh([ma.time_slot for ma in self.area.all_markets])
        for market in self.area.all_markets:
            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                self.buy_energy(market)
            elif ConstSettings.IAASettings.MARKET_TYPE == 2 or \
                    ConstSettings.IAASettings.MARKET_TYPE == 3:

                if self.are_bids_posted(market):
                    self.update_posted_bids_over_ticks(market)
                else:
                    energy_kWh = self.state.energy_to_buy_dict[market.time_slot]
                    if energy_kWh > 0:
                        first_bid = self.post_first_bid(market, energy_kWh * 1000.0)
                        if first_bid is not None:
                            self.state.offered_buy_kWh[market.time_slot] += first_bid.energy

            self.state.tick(area, market.time_slot)
            if self.cap_price_strategy is False:
                self.decrease_energy_price_over_ticks(market)

    def event_trade(self, *, market_id, trade):
        market = self.area.get_future_market_from_id(market_id)
        super().event_trade(market_id=market_id, trade=trade)
        if trade.offer.seller == self.owner.name:
            self.state.pledged_sell_kWh[market.time_slot] += trade.offer.energy
            self.state.offered_sell_kWh[market.time_slot] -= trade.offer.energy

    def event_bid_traded(self, *, market_id, bid_trade):
        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)
        market = self.area.get_future_market_from_id(market_id)

        if bid_trade.offer.buyer == self.owner.name:
            self.state.pledged_buy_kWh[market.time_slot] += bid_trade.offer.energy
            self.state.offered_buy_kWh[market.time_slot] -= bid_trade.offer.energy

    def event_market_cycle(self):
        self.update_market_cycle_offers(self.break_even[self.area.now][1])
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
            self.update_market_cycle_bids(final_rate=self.break_even[
                self.area.now][0])
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
        max_affordable_offer_rate = self.break_even[market.time_slot][0]
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
                        self.accept_offer(market, offer, energy=max_energy)
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
            self.set_initial_selling_rate_alternative_pricing_scheme(market)

            selling_rate = self.calculate_selling_rate(market)
            energy = energy_sell_dict[market.time_slot]
            if not self.state.has_battery_reached_max_power(energy, market.time_slot):
                if energy > 0.0:
                    offer = market.offer(
                        energy * selling_rate,
                        energy,
                        self.owner.name
                    )
                    self.offers.post(offer, market)
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
            break_even_sell = self.break_even[market.time_slot][1]
            max_selling_rate = self.calculate_initial_sell_rate(market.time_slot)
            return max(max_selling_rate, break_even_sell)

    def capacity_dependant_sell_rate(self, market):
        if self.state.charge_history[market.time_slot] is '-':
            soc = self.state.used_storage / self.state.capacity
        else:
            soc = self.state.charge_history[market.time_slot] / 100.0
        max_selling_rate = self.calculate_initial_sell_rate(market.time_slot)
        break_even_sell = self.break_even[market.time_slot][1]
        if max_selling_rate < break_even_sell:
            return break_even_sell
        else:
            return max_selling_rate - (max_selling_rate - break_even_sell) * soc
