from typing import Union

from d3a.exceptions import MarketException
from d3a.models.state import StorageState
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import ConstSettings
from d3a.models.strategy.update_frequency import OfferUpdateFrequencyMixin, BidUpdateFrequencyMixin


class StorageStrategy(BaseStrategy, OfferUpdateFrequencyMixin, BidUpdateFrequencyMixin):
    parameters = ('risk', 'initial_capacity', 'initial_soc',
                  'battery_capacity', 'max_abs_battery_power')

    def __init__(self, risk: int=ConstSettings.DEFAULT_RISK,
                 initial_capacity: float=0.0,
                 initial_soc: float=None,
                 initial_rate_option: int=ConstSettings.INITIAL_ESS_RATE_OPTION,
                 energy_rate_decrease_option: int=ConstSettings.ESS_RATE_DECREASE_OPTION,
                 energy_rate_decrease_per_update: float=ConstSettings.ENERGY_RATE_DECREASE_PER_UPDATE,  # NOQA
                 battery_capacity: float=ConstSettings.STORAGE_CAPACITY,
                 max_abs_battery_power: float=ConstSettings.MAX_ABS_BATTERY_POWER,
                 break_even: Union[tuple, dict]=(ConstSettings.STORAGE_BREAK_EVEN_BUY,
                             ConstSettings.STORAGE_BREAK_EVEN_SELL),

                 cap_price_strategy: bool=False):
        break_even = self._update_break_even_points(break_even)
        self._validate_constructor_arguments(risk, initial_capacity,
                                             initial_soc, battery_capacity, break_even)
        self.break_even = break_even
        self.min_selling_rate = break_even[0][1]
        BaseStrategy.__init__(self)
        OfferUpdateFrequencyMixin.__init__(self, initial_rate_option,
                                           energy_rate_decrease_option,
                                           energy_rate_decrease_per_update)
        # TODO: Likewise to the load strategy, make the bid rates configurable
        BidUpdateFrequencyMixin.__init__(self,
                                         initial_rate=ConstSettings.STORAGE_MIN_BUYING_RATE,
                                         final_rate=ConstSettings.STORAGE_BREAK_EVEN_BUY)

        self.risk = risk
        self.state = StorageState(initial_capacity=initial_capacity,
                                  initial_soc=initial_soc,
                                  capacity=battery_capacity,
                                  max_abs_battery_power=max_abs_battery_power,
                                  loss_per_hour=0.0,
                                  strategy=self)
        self.cap_price_strategy = cap_price_strategy

    def event_activate(self):
        self.state.set_battery_energy_per_slot(self.area.config.slot_length)
        self.update_on_activate()

    def _update_break_even_points(self, break_even):
        if isinstance(break_even, tuple) or isinstance(break_even, list):
            return {i: (break_even[0], break_even[1]) for i in range(24)}
        if isinstance(break_even, dict):
            latest_entry = (ConstSettings.STORAGE_BREAK_EVEN_BUY,
                            ConstSettings.STORAGE_BREAK_EVEN_SELL)
            for i in range(24):
                if i not in break_even:
                    break_even[i] = latest_entry
                else:
                    latest_entry = break_even[i]
            return break_even
        else:
            raise ValueError("Break even point should be either a tuple for the buy/sell rate, "
                             "or an hourly dict of tuples.")

    @staticmethod
    def _validate_constructor_arguments(risk, initial_capacity, initial_soc,
                                        battery_capacity, break_even):
        if battery_capacity < 0:
            raise ValueError("Battery capacity should be a positive integer")
        if initial_soc and not 0 <= initial_soc <= 100:
            raise ValueError("Initial charge is a percentage value, should be between 0 and 100.")
        if not 0 <= risk <= 100:
            raise ValueError("Risk is a percentage value, should be between 0 and 100.")
        if initial_capacity and not 0 <= initial_capacity <= battery_capacity:
            raise ValueError("Initial capacity should be between 0 and "
                             "battery_capacity parameter.")
        if any(be[1] <= be[0] for _, be in break_even.items()):
            raise ValueError("Break even point for sell energy is lower than buy energy.")
        if any(break_even_point[0] < 0 or break_even_point[1] < 0
               for _, break_even_point in break_even.items()):
            raise ValueError("Break even point should be positive energy rate values.")

    def event_tick(self, *, area):
        # Check if there are cheap offers to buy
        if ConstSettings.INTER_AREA_AGENT_MARKET_TYPE == 1:
            self.buy_energy()
            if self.cap_price_strategy is False:
                self.decrease_energy_price_over_ticks()
        elif ConstSettings.INTER_AREA_AGENT_MARKET_TYPE == 2:
            if self.state.clamp_energy_to_buy_kWh() <= 0:
                return
            if self.are_bids_posted(self.area.next_market):
                self.update_posted_bids(self.area.next_market)
            else:
                # TODO: Refactor this to reuse all markets
                self.post_first_bid(
                    self.area.next_market,
                    self.state.clamp_energy_to_buy_kWh() * 1000.0
                )

        self.state.tick(area)  # To incorporate battery energy loss over time

    def event_bid_deleted(self, *, market, bid):
        if ConstSettings.INTER_AREA_AGENT_MARKET_TYPE == 1:
            # Do not handle bid deletes on single sided markets
            return
        if market != self.area.next_market:
            return
        if bid.buyer != self.owner.name:
            return
        self.remove_bid_from_pending(bid.id, self.area.next_market)

    def event_bid_traded(self, *, market, traded_bid):
        if ConstSettings.INTER_AREA_AGENT_MARKET_TYPE == 1:
            # Do not handle bid trades on single sided markets
            assert False and "Invalid state, cannot receive a bid if single sided market" \
                             " is globally configured."

        if traded_bid.offer.buyer != self.owner.name:
            return

        buffered_bid = next(filter(
            lambda b: b.id == traded_bid.offer.id, self.get_posted_bids(market)
        ))

        if traded_bid.offer.buyer == buffered_bid.buyer:
            # Update energy requirement and clean up the pending bid buffer
            self.state.update_energy_per_slot(-traded_bid.offer.energy, market.time_slot)
            self.state.block_storage(traded_bid.offer.energy)
            self.add_bid_to_bought(traded_bid.offer, market)

    def event_market_cycle(self):
        self.update_market_cycle(self.break_even[self.area.now.hour][1])
        if self.area.past_markets:
            past_market = list(self.area.past_markets.values())[-1]
        else:
            if self.state.used_storage > 0:
                self.sell_energy()
            return
        # if energy in this slot was bought: update the storage
        for bought in self.offers.bought_in_market(past_market):
            self.state.fill_blocked_storage(bought.energy)
            self.sell_energy(energy=bought.energy)
        for traded in self.get_traded_bids_from_market(past_market):
            self.state.fill_blocked_storage(traded.energy)
        # if energy in this slot was sold: update the storage
        for sold in self.offers.sold_in_market(past_market):
            self.state.sold_offered_storage(sold.energy)
        # Check if Storage posted offer in that market that has not been bought
        # If so try to sell the offer again
        for offer in self.offers.open_in_market(past_market):
            self.sell_energy(offer.energy, open_offer=True)
            self.offers.sold_offer(offer.id, past_market)
        # sell remaining capacity too (e. g. initial capacity)
        if self.state.used_storage > 0:
            self.sell_energy()
        self.state.market_cycle(self.area)

        if ConstSettings.INTER_AREA_AGENT_MARKET_TYPE == 2:
            self.update_on_market_cycle(self.break_even[self.area.now.hour][1])
            if self.state.clamp_energy_to_buy_kWh() > 0:
                self.post_first_bid(
                    self.area.next_market,
                    self.state.clamp_energy_to_buy_kWh() * 1000.0
                )

    def buy_energy(self):
        # Here starts the logic if energy should be bought
        # Iterating over all offers in every open market
        for market in self.area.markets.values():
            max_affordable_offer_rate = self.break_even[market.time_slot.hour][0]
            for offer in market.sorted_offers:
                if offer.seller == self.owner.name:
                    # Don't buy our own offer
                    continue
                # Check if storage has free capacity and if the price is cheap enough
                if self.state.free_storage > 0.0 \
                        and (offer.price / offer.energy) < max_affordable_offer_rate:
                    # Try to buy the energy
                    try:
                        if not self.state.has_battery_reached_max_power(market.time_slot):
                            max_energy = self.state.clamp_energy_to_buy_kWh(offer.energy)
                            self.accept_offer(market, offer, energy=max_energy)
                            self.state.update_energy_per_slot(-max_energy, market.time_slot)
                            self.state.block_storage(max_energy)
                            return True

                    except MarketException:
                        # Offer already gone etc., try next one.
                        return False
                else:
                    return False

    def sell_energy(self, energy=None, open_offer=False):
        target_market = self._select_market_to_sell()
        selling_rate = self._calculate_selling_rate(target_market)
        energy = self._calculate_energy_to_sell(energy, target_market)

        if energy > 0.0:
            offer = target_market.offer(
                energy * selling_rate,
                energy,
                self.owner.name
            )
            self.state.update_energy_per_slot(energy, target_market.time_slot)

            # Update only for new offers
            # Offers that were open before should not be updated
            if not open_offer:
                self.state.offer_storage(energy)
            self.offers.post(offer, target_market)

    def _select_market_to_sell(self):
        if ConstSettings.STORAGE_SELL_ON_MOST_EXPENSIVE_MARKET:
            # Sell on the most expensive market
            try:
                max_rate = 0.0
                most_expensive_market = list(self.area.markets.values())[0]
                for m in self.area.markets.values():
                    if len(m.sorted_offers) > 0 and \
                            m.sorted_offers[0].price / m.sorted_offers[0].energy > max_rate:
                        max_rate = m.sorted_offers[0].price / m.sorted_offers[0].energy
                        most_expensive_market = m
            except IndexError:
                try:
                    most_expensive_market = self.area.current_market
                except StopIteration:
                    return
            return most_expensive_market
        else:
            # Sell on the most recent future market
            return list(self.area.markets.values())[0]

    def _calculate_energy_to_sell(self, energy, target_market):
        # If there is not enough available energy for this timeslot, then return 0 energy
        if self.state.has_battery_reached_max_power(target_market.time_slot):
            return 0.0

        energy = self.state.clamp_energy_to_sell_kWh(energy, target_market.time_slot)
        return energy

    def _calculate_selling_rate(self, market):
        if self.cap_price_strategy is True:
            return self.capacity_dependant_sell_rate(market)
        else:
            break_even_sell = self.break_even[market.time_slot.hour][1]
            max_selling_rate = self._max_selling_rate(market)
            return max(max_selling_rate, break_even_sell)

    def _max_selling_rate(self, market):
        if self.initial_rate_option == 1 and self.area.historical_avg_rate != 0:
            return self.area.historical_avg_rate
        else:
            return self.area.config.market_maker_rate[market.time_slot.hour]

    def capacity_dependant_sell_rate(self, market):
        if self.state.charge_history[market.time_slot] is '-':
            soc = self.state.used_storage / self.state.capacity
        else:
            soc = self.state.charge_history[market.time_slot]

        max_selling_rate = self._max_selling_rate(market)
        break_even_sell = self.break_even[market.time_slot.hour][1]
        if max_selling_rate < break_even_sell:
            return break_even_sell
        else:
            return max_selling_rate - (max_selling_rate - break_even_sell) * soc
