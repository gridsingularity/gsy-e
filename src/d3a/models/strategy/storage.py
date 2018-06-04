from d3a.models.strategy import ureg, Q_

from d3a.exceptions import MarketException
from d3a.models.state import StorageState
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import DEFAULT_RISK, MAX_RISK,\
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
        super().__init__()
        self.risk = risk
        self.state = StorageState(initial_capacity=initial_capacity,
                                  initial_charge=initial_charge,
                                  capacity=battery_capacity,
                                  max_abs_battery_power=max_abs_battery_power,
                                  loss_per_hour=0.0,
                                  strategy=self)
        self.break_even = Q_(break_even, (ureg.EUR_cents/ureg.kWh))
        self.max_selling_rate_cents_per_kwh =\
            Q_(max_selling_rate_cents_per_kwh, (ureg.EUR_cents/ureg.kWh))
        self.cap_price_strategy = cap_price_strategy

    def event_activate(self):
        self.state.battery_energy_per_slot(self.area.config.slot_length)

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
            self.sell_energy(buying_rate=(bought.price/bought.energy),
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

            initial_buying_rate = (
                                        (offer_rate / 1.01) *
                                        (1 / (1.1 - (0.1 * (self.risk / MAX_RISK))))
                                    )
            self.sell_energy(initial_buying_rate, offer.energy, open_offer=True)
            self.offers.sold_offer(offer.id, past_market)
        # sell remaining capacity too (e. g. initial capacity)
        if self.state.used_storage > 0:
            self.sell_energy(self.find_most_expensive_market_rate())
        self.state.market_cycle(self.area)

    def buy_energy(self, avg_cheapest_offer_rate):
        # Here starts the logic if energy should be bought
        # Iterating over all offers in every open market
        for market in self.area.markets.values():
            for offer in market.sorted_offers:
                if offer.seller == self.owner.name:
                    # Don't buy our own offer
                    continue
                # Check if storage has free capacity and if the price is cheap enough
                if (self.state.free_storage >= offer.energy
                        and (self.state.available_energy_per_slot(market.time_slot) > offer.energy)
                        and (offer.price / offer.energy) < (avg_cheapest_offer_rate * 0.99)):
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
        # Highest risk selling price using the highest risk is 20% above the average price
        min_selling_rate = 1.01 * buying_rate
        # This ends up in a selling price between 101 and 105 percentage of the buying price
        risk_dependent_selling_rate = (
            min_selling_rate * (1.1 - (0.1 * (self.risk / MAX_RISK)))
        )
        # Find the most expensive offer out of the list of cheapest offers
        # in currently open markets
        try:
            most_expensive_market = self.area.market_with_most_expensive_offer
        except IndexError:
            try:
                most_expensive_market = next(iter(self.area.markets.values()))
            except StopIteration:
                return
        # If no energy is passed, try to sell all the Energy left in the storage
        if energy is None:
            energy = self.state.used_storage
        # Try to create an offer to sell the stored energy

        # selling should be more than break-even price
        if (energy > 0.0
                and self.state.available_energy_per_slot(most_expensive_market.time_slot)
                > energy):
            if self.cap_price_strategy:
                offer = most_expensive_market.offer(
                    energy * self.capacity_dependant_sell_rate(),
                    energy,
                    self.owner.name
                )
                self.state.update_energy_per_slot(energy, most_expensive_market.time_slot)
            else:
                offer = most_expensive_market.offer(
                    energy * max(risk_dependent_selling_rate, self.break_even.m),
                    energy,
                    self.owner.name
                )
            self.state.update_energy_per_slot(energy, most_expensive_market.time_slot)
            # Updating parameters
            if not open_offer:
                self.state.offer_storage(energy)
            self.offers.post(offer, most_expensive_market)

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
            most_expensive_cheapest_offer = self.break_even.m
        return min(most_expensive_cheapest_offer, self.break_even.m)

    def capacity_dependant_sell_rate(self):
        most_recent_past_ts = sorted(self.area.past_markets.keys())

        if len(self.area.past_markets.keys()) > 1:
            charge_per = self.state.charge_history[most_recent_past_ts[-2]]
            rate = self.max_selling_rate_cents_per_kwh -\
                ((self.max_selling_rate_cents_per_kwh-self.break_even)*(charge_per/100))
            return rate.m
        else:
            return self.max_selling_rate_cents_per_kwh.m
