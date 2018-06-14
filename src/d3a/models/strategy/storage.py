from d3a.models.strategy import ureg, Q_

from d3a.exceptions import MarketException
from d3a.models.state import StorageState
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import DEFAULT_RISK, MAX_RISK, STORAGE_MIN_ALLOWED_SOC, \
    STORAGE_BREAK_EVEN, STORAGE_MAX_SELL_RATE_c_per_Kwh, STORAGE_CAPACITY, MAX_ABS_BATTERY_POWER


class StorageStrategy(BaseStrategy):
    parameters = ('risk', 'initial_capacity', 'initial_charge',
                  'battery_capacity', 'max_abs_battery_power')

    def __init__(self, risk=DEFAULT_RISK,
                 initial_capacity=0.0,
                 initial_charge=None,
                 battery_capacity=STORAGE_CAPACITY,
                 max_abs_battery_power=MAX_ABS_BATTERY_POWER,
                 break_even=STORAGE_BREAK_EVEN,
                 max_selling_rate_cents_per_kwh=STORAGE_MAX_SELL_RATE_c_per_Kwh,
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
        self.max_selling_rate_cents_per_kwh = \
            Q_(max_selling_rate_cents_per_kwh, (ureg.EUR_cents / ureg.kWh))
        self.cap_price_strategy = cap_price_strategy

    def event_activate(self):
        self.state.battery_energy_per_slot(self.area.config.slot_length)

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
        # Taking the cheapest offers in every market currently open and building the average
        # avg_cheapest_offer_price = self.find_avg_cheapest_offers()
        most_expensive_offer_rate = self.find_most_expensive_market_rate()
        # Check if there are cheap offers to buy
        self.buy_energy(most_expensive_offer_rate)
        self.state.tick(area)

    def event_market_cycle(self):
        if self.area.past_markets:
            past_market = list(self.area.past_markets.values())[-1]
        else:
            if self.state.used_storage > 0:
                self.sell_energy(self.find_most_expensive_market_rate())
            return
        # if energy in this slot was bought: update the storage
        for bought in self.offers.bought_in_market(past_market):
            self.state.fill_blocked_storage(bought.energy)
            self.sell_energy(buying_rate=(bought.price / bought.energy),
                             energy=bought.energy)
        # if energy in this slot was sold: update the storage
        for sold in self.offers.sold_in_market(past_market):
            self.state.sold_offered_storage(sold.energy)
        # Check if Storage posted offer in that market that has not been bought
        # If so try to sell the offer again
        for offer in self.offers.open_in_market(past_market):
            # self.offers_posted[market].price is the price we charged including profit
            # But self.sell_energy expects a buying price
            offer_rate = (offer.price / offer.energy)

            initial_buying_rate = offer_rate / (1.01 * self._risk_factor)

            self.sell_energy(initial_buying_rate, offer.energy, open_offer=True)
            self.offers.sold_offer(offer.id, past_market)
        # sell remaining capacity too (e. g. initial capacity)
        if self.state.used_storage > 0:
            self.sell_energy(self.find_most_expensive_market_rate())
        self.state.market_cycle(self.area)

    def buy_energy(self, avg_cheapest_offer_rate):
        # Here starts the logic if energy should be bought
        # Iterating over all offers in every open market
        max_affordable_offer_rate = min(avg_cheapest_offer_rate*0.99, self.break_even.m-0.01)
        for market in self.area.markets.values():
            for offer in market.sorted_offers:
                if offer.seller == self.owner.name:
                    # Don't buy our own offer
                    continue
                # Check if storage has free capacity and if the price is cheap enough
                if self.state.free_storage >= offer.energy \
                        and self.state.available_energy_per_slot(market.time_slot) > offer.energy \
                        and (offer.price / offer.energy) < max_affordable_offer_rate:
                    # Try to buy the energy
                    try:
                        self.accept_offer(market, offer)
                        self.state.update_energy_per_slot(offer.energy, market.time_slot)
                        self.state.block_storage(offer.energy)
                        return True
                    except MarketException:
                        # Offer already gone etc., try next one.
                        return False
                else:
                    return False

    def sell_energy(self, buying_rate, energy=None, open_offer=False):
        selling_rate = self._calculate_selling_rate_from_buying_rate(buying_rate)
        assert buying_rate > 0.0

        target_market = self._select_market_to_sell()
        energy = self._calculate_energy_to_sell(energy, target_market)

        if energy > 0.0:
            assert selling_rate > 0.0
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

    def _calculate_energy_to_sell(self, energy, target_market):
        # If no energy is passed, try to sell all the Energy left in the storage
        if energy is None:
            energy = self.state.used_storage

        # Limit energy according to the maximum battery power
        energy = min(energy, self.state.available_energy_per_slot(target_market.time_slot))
        # Limit energy to respect minimum allowed battery SOC
        target_soc = (self.state.used_storage + self.state.offered_storage - energy) / \
            self.state.capacity
        if STORAGE_MIN_ALLOWED_SOC > target_soc:
            energy = self.state.used_storage + self.state.offered_storage - \
                     self.state.capacity * STORAGE_MIN_ALLOWED_SOC
        return energy

    def _calculate_selling_rate_from_buying_rate(self, buying_rate):
        if self.cap_price_strategy is True:
            return self.capacity_dependant_sell_rate()
        min_selling_rate = 1.01 * buying_rate
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
        return 1.1 - (0.1 * (self.risk / MAX_RISK))

    def find_avg_cheapest_offers(self):
        # Taking the cheapest offers in every market currently open and building the average
        cheapest_offers = self.area.cheapest_offers
        avg_cheapest_offer_rate = (
                sum((offer.price / offer.energy) for offer in cheapest_offers)
                / max(len(cheapest_offers), 1)
        )
        return min(avg_cheapest_offer_rate, self.break_even.m)

    def find_most_expensive_market_rate(self):
        cheapest_offers = self.area.cheapest_offers
        if len(cheapest_offers) != 0:
            most_expensive_cheapest_offer = (
                max((offer.price / offer.energy) for offer in cheapest_offers))
        else:
            most_expensive_cheapest_offer = 30
        return max(
            min(most_expensive_cheapest_offer, self.max_selling_rate_cents_per_kwh.m),
            self.break_even.m
        )

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
