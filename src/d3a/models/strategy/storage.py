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
from d3a.models.strategy import BaseStrategy
from d3a.models.const import ConstSettings
from d3a.models.strategy.update_frequency import OfferUpdateFrequencyMixin, \
    BidUpdateFrequencyMixin, InitialRateOptions
from d3a.models.read_user_profile import read_arbitrary_profile
from d3a.models.read_user_profile import InputProfileTypes
from d3a.constants import TIME_FORMAT
from d3a.d3a_core.device_registry import DeviceRegistry

BalancingRatio = namedtuple('BalancingRatio', ('demand', 'supply'))

StorageSettings = ConstSettings.StorageSettings
GeneralSettings = ConstSettings.GeneralSettings
BalancingSettings = ConstSettings.BalancingSettings


class StorageStrategy(BaseStrategy, OfferUpdateFrequencyMixin, BidUpdateFrequencyMixin):
    parameters = ('risk', 'initial_capacity_kWh', 'initial_soc', 'initial_rate_option',
                  'energy_rate_decrease_option', 'energy_rate_decrease_per_update',
                  'battery_capacity_kWh', 'max_abs_battery_power_kW', 'break_even',
                  'initial_selling_rate')

    def __init__(self, risk: int=GeneralSettings.DEFAULT_RISK,
                 initial_capacity_kWh: float=None,
                 initial_soc: float=None,
                 initial_rate_option: int=StorageSettings.INITIAL_RATE_OPTION,
                 initial_selling_rate:
                 float=ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
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

        if type(break_even) == list:
            break_even = tuple(break_even)

        if min_allowed_soc is None:
            min_allowed_soc = StorageSettings.MIN_ALLOWED_SOC
        break_even = read_arbitrary_profile(InputProfileTypes.IDENTITY, break_even)
        self.initial_selling_rate = initial_selling_rate

        self._validate_constructor_arguments(risk, initial_capacity_kWh,
                                             initial_soc, battery_capacity_kWh, break_even,
                                             min_allowed_soc, initial_selling_rate)
        self.break_even = break_even

        self.min_selling_rate = list(break_even.values())[0][1]
        BaseStrategy.__init__(self)
        OfferUpdateFrequencyMixin.__init__(self, initial_rate_option,
                                           initial_selling_rate,
                                           energy_rate_decrease_option,
                                           energy_rate_decrease_per_update)
        # Normalize min/max buying rate profiles before passing to the bid mixin
        self.min_buying_rate_profile = read_arbitrary_profile(
            InputProfileTypes.IDENTITY,
            StorageSettings.MIN_BUYING_RATE
        )
        self.max_buying_rate_profile = {k: v[1] for k, v in break_even.items()}
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

    def event_activate(self):
        self.update_market_cycle_offers(self.break_even[self.area.now.strftime(TIME_FORMAT)][1])
        self.state.set_battery_energy_per_slot(self.area.config.slot_length)
        self.update_on_activate()

    @staticmethod
    def _validate_constructor_arguments(risk, initial_capacity_kWh, initial_soc,
                                        battery_capacity_kWh, break_even, min_allowed_soc,
                                        initial_selling_rate):
        if battery_capacity_kWh < 0:
            raise ValueError("Battery capacity should be a positive integer")
        if initial_soc and not min_allowed_soc <= initial_soc <= 100:
            raise ValueError("Initial charge is a percentage value, should be between "
                             "MIN_ALLOWED_SOC and 100.")
        if not 0 <= risk <= 100:
            raise ValueError("Risk is a percentage value, should be between 0 and 100.")
        min_allowed_capacity = min_allowed_soc * battery_capacity_kWh
        if initial_capacity_kWh and not min_allowed_capacity \
           <= initial_capacity_kWh <= battery_capacity_kWh:
            raise ValueError(f"Initial capacity should be between min_allowed_capacity and "
                             "battery_capacity_kWh parameter.")
        if any(be[1] < be[0] for _, be in break_even.items()):
            raise ValueError("Break even point for sell energy is lower than buy energy.")
        if any(break_even_point[0] < 0 or break_even_point[1] < 0
               for _, break_even_point in break_even.items()):
            raise ValueError("Break even point should be positive energy rate values.")
        if initial_selling_rate < 0:
            raise ValueError("Initial selling rate must be greater equal 0.")

    def event_tick(self, *, area):
        self.state.clamp_energy_to_buy_kWh([ma.time_slot for ma in self.area.all_markets])
        for market in self.area.all_markets:
            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                self.buy_energy(market)
            elif ConstSettings.IAASettings.MARKET_TYPE == 2:

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

    def event_bid_deleted(self, *, market_id, bid):
        if ConstSettings.IAASettings.MARKET_TYPE == 1:
            # Do not handle bid deletes on single sided markets
            return
        if market_id != self.area.next_market.id:
            return
        if bid.buyer != self.owner.name:
            return
        self.remove_bid_from_pending(bid.id, self.area.next_market)

    def event_bid_traded(self, *, market_id, bid_trade):
        if ConstSettings.IAASettings.MARKET_TYPE == 1:
            # Do not handle bid trades on single sided markets
            assert False and "Invalid state, cannot receive a bid if single sided market" \
                             " is globally configured."

        if bid_trade.offer.buyer != self.owner.name:
            return
        market = self.area.get_future_market_from_id(market_id)
        assert market is not None

        buffered_bid = next(filter(
            lambda b: b.id == bid_trade.offer.id, self.get_posted_bids(market)
        ))

        if bid_trade.offer.buyer == buffered_bid.buyer:
            # Do not remove bid in case the trade is partial
            self.add_bid_to_bought(bid_trade.offer, market, remove_bid=not bid_trade.residual)
            self.state.pledged_buy_kWh[market.time_slot] += bid_trade.offer.energy
            self.state.offered_buy_kWh[market.time_slot] -= bid_trade.offer.energy

    def event_market_cycle(self):
        self.update_market_cycle_offers(self.break_even[self.area.now.strftime(TIME_FORMAT)][1])
        current_market = self.area.next_market
        past_market = self.area.last_past_market

        self.state.market_cycle(
            past_market.time_slot if past_market else current_market.time_slot,
            current_market.time_slot
        )

        if self.state.used_storage > 0:
            self.sell_energy()

        if ConstSettings.IAASettings.MARKET_TYPE == 2:
            self.state.clamp_energy_to_buy_kWh([current_market.time_slot])
            self.update_market_cycle_bids(final_rate=self.break_even[
                self.area.now.strftime(TIME_FORMAT)][0])
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
        max_affordable_offer_rate = self.break_even[market.time_slot_str][0]
        for offer in market.sorted_offers:
            if offer.seller == self.owner.name:
                # Don't buy our own offer
                continue
            # Check if storage has free capacity and if the price is cheap enough
            if self.state.free_storage(market.time_slot) > 0.0 \
                    and (offer.price / offer.energy) < max_affordable_offer_rate:
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
            break_even_sell = self.break_even[market.time_slot_str][1]
            max_selling_rate = self._max_selling_rate(market)
            return max(max_selling_rate, break_even_sell)

    def _max_selling_rate(self, market):
        if self.initial_rate_option == InitialRateOptions.HISTORICAL_AVG_RATE \
                and self.area.historical_avg_rate != 0:
            return self.area.historical_avg_rate
        elif self.initial_rate_option == InitialRateOptions.MARKET_MAKER_RATE:
            return self.area.config.market_maker_rate[market.time_slot_str]
        elif self.initial_rate_option == InitialRateOptions.CUSTOM_RATE:
            return self.initial_selling_rate

    def capacity_dependant_sell_rate(self, market):
        if self.state.charge_history[market.time_slot] is '-':
            soc = self.state.used_storage / self.state.capacity
        else:
            soc = self.state.charge_history[market.time_slot] / 100.0
        max_selling_rate = self._max_selling_rate(market)
        break_even_sell = self.break_even[market.time_slot_str][1]
        if max_selling_rate < break_even_sell:
            return break_even_sell
        else:
            return max_selling_rate - (max_selling_rate - break_even_sell) * soc
