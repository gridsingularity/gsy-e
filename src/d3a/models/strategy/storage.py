from d3a.models.strategy import ureg, Q_

from d3a.exceptions import MarketException
from d3a.models.state import StorageState
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import ConstSettings


class StorageStrategy(BaseStrategy):
    parameters = ('risk', 'initial_capacity', 'initial_charge',
                  'battery_capacity', 'max_abs_battery_power')

    def __init__(self, risk=ConstSettings.DEFAULT_RISK,
                 initial_capacity=0.0,
                 initial_charge=None,
                 battery_capacity=ConstSettings.STORAGE_CAPACITY,
                 max_abs_battery_power=ConstSettings.MAX_ABS_BATTERY_POWER,
                 break_even=ConstSettings.STORAGE_BREAK_EVEN,
                 cap_price_strategy=False):
        self._validate_constructor_arguments(risk, initial_capacity,
                                             initial_charge, battery_capacity)
        super().__init__()
        self.risk = risk
        self.state = StorageState(initial_capacity=initial_capacity,
                                  initial_charge=initial_charge,
                                  capacity=battery_capacity,
                                  max_abs_battery_power=max_abs_battery_power,
                                  loss_per_hour=0.0,
                                  strategy=self)
        self.break_even = Q_(break_even, (ureg.EUR_cents / ureg.kWh))
        self.cap_price_strategy = cap_price_strategy

    def event_activate(self):
        self.state.battery_energy_per_slot(self.area.config.slot_length)
        self.max_selling_rate_cents_per_kwh = \
            Q_((self.area.config.market_maker_rate-1), (ureg.EUR_cents / ureg.kWh))

    @staticmethod
    def _validate_constructor_arguments(risk, initial_capacity, initial_charge, battery_capacity):
        if battery_capacity < 0:
            raise ValueError("Battery capacity should be a positive integer")
        if initial_charge and not 0 <= initial_charge <= 100:
            raise ValueError("Initial charge is a percentage value, should be between 0 and 100.")
        if not 0 <= risk <= 100:
            raise ValueError("Risk is a percentage value, should be between 0 and 100.")
        if initial_capacity and not 0 <= initial_capacity <= battery_capacity:
            raise ValueError("Initial capacity should be between 0 and "
                             "battery_capacity parameter.")

    def event_tick(self, *, area):
        # Check if there are cheap offers to buy
        self.buy_energy()
        self.state.tick(area)

    def event_market_cycle(self):
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

    def buy_energy(self):
        # Here starts the logic if energy should be bought
        # Iterating over all offers in every open market
        max_affordable_offer_rate = self.break_even.m-0.01
        for market in self.area.markets.values():
            for offer in market.sorted_offers:
                if offer.seller == self.owner.name:
                    # Don't buy our own offer
                    continue
                # Check if storage has free capacity and if the price is cheap enough
                if self.state.free_storage >= offer.energy \
                        and (offer.price / offer.energy) < max_affordable_offer_rate:
                    # Try to buy the energy
                    try:
                        if self.state.available_energy_per_slot(market.time_slot) > offer.energy:
                            max_energy = offer.energy
                        else:
                            max_energy = self.state.available_energy_per_slot(market.time_slot)
                        self.accept_offer(market, offer, energy=max_energy)
                        self.state.update_energy_per_slot(max_energy, market.time_slot)
                        self.state.block_storage(max_energy)
                        return True

                    except MarketException:
                        # Offer already gone etc., try next one.
                        return False
                else:
                    return False

    def sell_energy(self, energy=None, open_offer=False):
        selling_rate = self._calculate_selling_rate_from_buying_rate()

        target_market = self._select_market_to_sell()
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
        # If no energy is passed, try to sell all the Energy left in the storage
        if energy is None:
            energy = self.state.used_storage

        # Limit energy according to the maximum battery power
        energy = min(energy, self.state.available_energy_per_slot(target_market.time_slot))
        # Limit energy to respect minimum allowed battery SOC
        target_soc = (self.state.used_storage + self.state.offered_storage - energy) / \
            self.state.capacity
        if ConstSettings.STORAGE_MIN_ALLOWED_SOC > target_soc:
            energy = self.state.used_storage + self.state.offered_storage - \
                     self.state.capacity * ConstSettings.STORAGE_MIN_ALLOWED_SOC
        return energy

    def _calculate_selling_rate_from_buying_rate(self):
        if self.cap_price_strategy is True:
            return self.capacity_dependant_sell_rate()
        min_selling_rate = self.break_even.m+0.01
        # This ends up in a selling price between 101 and 105 percentage of the buying price
        risk_dependent_selling_rate = (
                min_selling_rate * self._risk_factor
        )
        # Limit rate to respect max sell rate
        return max(
            min(risk_dependent_selling_rate, self.max_selling_rate_cents_per_kwh.m),
            self.break_even.m
        )

    @property
    def _risk_factor(self):
        return 1.1 - (0.1 * (self.risk / ConstSettings.MAX_RISK))

    def capacity_dependant_sell_rate(self):
        most_recent_past_ts = sorted(self.area.past_markets.keys())

        if len(self.area.past_markets.keys()) > 1:
            # TODO: Why the -2 here?
            charge_per = self.state.charge_history[most_recent_past_ts[-2]]
            # TODO: max_selling_rate_cents_per_kwh is never mutating and is valid
            # TODO: only in capacity depending strategy
            # TODO: Should remain const or be abstracted from this class
            rate = self.max_selling_rate_cents_per_kwh - \
                ((self.max_selling_rate_cents_per_kwh - self.break_even) * (charge_per / 100))
            return rate.m
        else:
            return self.max_selling_rate_cents_per_kwh.m
