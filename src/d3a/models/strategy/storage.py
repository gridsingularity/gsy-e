from collections import defaultdict
from typing import Dict, List  # noqa

from d3a.exceptions import MarketException
from d3a.models.market import Market, Offer, log  # noqa
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import DEFAULT_RISK, STORAGE_CAPACITY, MAX_RISK


class StorageStrategy(BaseStrategy):
    def __init__(self, risk=DEFAULT_RISK):
        super().__init__()
        self.risk = risk
        self.offers_posted = defaultdict(list)  # type: Dict[Market, List[Offer]]
        self.bought_offers = defaultdict(list)  # type: Dict[Market, List[Offer]]
        self.sold_offers = defaultdict(list)  # type: Dict[Market, List[Offer]]
        self.used_storage = 0.00
        self.offered_storage = 0.00
        self.blocked_storage = 0.00
        self.selling_price = 30

    def event_tick(self, *, area):
        # The storage looses 1% of capacity per hour
        # self.used_storage *= (1 - ((0.01 * self.area.config.tick_length.total_seconds())
        #                           / (60 * 60)
        #                           )
        #                      )
        # Taking the cheapest offers in every market currently open and building the average
        # avg_cheapest_offer_price = self.find_avg_cheapest_offers()
        most_expensive_offer_price = self.find_most_expensive_market_price()
        # Check if there are cheap offers to buy
        self.buy_energy(most_expensive_offer_price)

        # Log a warning if the capacity reaches 80%
        if (
                    (self.used_storage + self.offered_storage + self.blocked_storage)
                    > (0.8 * STORAGE_CAPACITY)
        ):
            self.log.info("Storage reached more than 80% Battery: %s", (self.used_storage
                                                                        / STORAGE_CAPACITY))

    def event_market_cycle(self):
        past_market = list(self.area.past_markets.values())[-1]
        # if energy in this slot was bought: update the storage
        for bought in self.bought_offers[past_market]:
            self.blocked_storage -= bought.energy
            self.used_storage += bought.energy
            self.sell_energy(buying_price=(bought.price / bought.energy), energy=bought.energy)
        # if energy in this slot was sold: update the storage
        for sold in self.sold_offers[past_market]:
            self.offered_storage -= sold.energy
        # Check if Storage posted offer in that market that has not been bought
        # If so try to sell the offer again
        if past_market in self.offers_posted.keys():
            for offer in list(self.offers_posted[past_market]):
                # self.offers_posted[market].price is the price we charged including profit
                # But self.sell_energy expects a buying price
                offer_price = (offer.price /
                               offer.energy)

                initial_buying_price = (
                                            (offer_price / 1.01) *
                                            (1 / (1.1 - (0.1 * (self.risk / MAX_RISK))))
                                         )
                self.sell_energy(initial_buying_price, offer.energy)
                self.offers_posted[past_market].remove(offer)

    def event_trade(self, *, market, trade):
        # If trade happened: remember it in variable
        if self.owner.name == trade.seller:
            self.sold_offers[market].append(trade.offer)
            self.offers_posted[market].remove(trade.offer)

    def buy_energy(self, avg_cheapest_offer_price):
        # Here starts the logic if energy should be bought
        # Iterating over all offers in every open market
        for market in self.area.markets.values():
            for offer in market.sorted_offers:
                if offer.seller == self.owner.name:
                    # Don't buy our own offer
                    continue
                # Check if storage has free capacity and if the price is cheap enough
                if (
                            (self.used_storage + self.blocked_storage + offer.energy
                             + self.offered_storage <= STORAGE_CAPACITY
                             )
                        and (offer.price / offer.energy) < (avg_cheapest_offer_price * 0.99)
                ):
                    # Try to buy the energy
                    try:
                        self.accept_offer(market, offer)
                        self.blocked_storage += offer.energy
                        self.bought_offers[market].append(offer)
                        return True
                    except MarketException:
                        # Offer already gone etc., try next one.
                        return False
                else:
                    return False

    def sell_energy(self, buying_price, energy=None):
        # Highest risk selling price using the highest risk is 20% above the average price
        min_selling_price = 1.01 * buying_price
        # This ends up in a selling price between 101 and 105 percentage of the buying price
        risk_dependent_selling_price = (
            min_selling_price * (1.1 - (0.1 * (self.risk / MAX_RISK)))
        )
        # Find the most expensive offer out of the list of cheapest offers
        # in currently open markets
        try:
            expensive_offers = list(self.area.cheapest_offers)[-1]
        except IndexError:
            return
        most_expensive_market = expensive_offers.market
        # If no energy is passed, try to sell all the Energy left in the storage
        if energy is None:
            energy = self.used_storage
        # Try to create an offer to sell the stored energy

        if energy > 0.0:
            offer = most_expensive_market.offer(
                energy * min(risk_dependent_selling_price, 29.9),
                energy,
                self.owner.name
            )
            # Updating parameters
            self.used_storage -= energy
            self.offered_storage += energy
            self.offers_posted[most_expensive_market].append(offer)

    def find_avg_cheapest_offers(self):
        # Taking the cheapest offers in every market currently open and building the average
        cheapest_offers = self.area.cheapest_offers
        avg_cheapest_offer_price = (
            sum((offer.price / offer.energy) for offer in cheapest_offers)
            / max(len(cheapest_offers), 1)
        )
        return min(avg_cheapest_offer_price, 30)

    def find_most_expensive_market_price(self):
        cheapest_offers = self.area.cheapest_offers
        if len(cheapest_offers) != 0:
            most_expensive_cheapest_offer = (
                max((offer.price / offer.energy) for offer in cheapest_offers))
        else:
            most_expensive_cheapest_offer = 30
        return min(most_expensive_cheapest_offer, 30)
