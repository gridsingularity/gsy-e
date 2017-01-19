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
        self.offers_posted = {}  # type: Dict[Market, Offer]
        self.bought_offers = defaultdict(list)  # type: Dict[Market, List[Offer]]
        self.sold_offers = defaultdict(list)  # type: Dict[Market, List[Offer]]
        self.used_storage = 0.00
        self.offered_storage = 0.00
        self.blocked_storage = 0.00
        self.selling_price = 30

    def event_tick(self, *, area):
        # The storage looses 1% of capacity per hour
        # TODO: reactivate me
        #        self.used_storage *= (1 - ((0.01 * self.area.config.tick_length.total_seconds())
        #                                   / (60 * 60)
        #                                   )
        #                              )
        # Taking the cheapest offers in every market currently open and building the average
        avg_cheapest_offer_price = self.find_avg_cheapest_offers()
        # Check if there are cheap offers to buy
        if self.buy_energy(avg_cheapest_offer_price):
            # Check if any energy from the storage can be sold
            accepted_offers = []
            for offers in list(self.bought_offers.values()):
                for o in offers:
                    accepted_offers.append((o.price / o.energy, o.energy))
            (price, energy) = accepted_offers[-1]
            self.sell_energy(price, energy)

        if self.used_storage > (0.8 * STORAGE_CAPACITY):
            self.log.info("Storage reached more than 80% Battery: %s", (self.used_storage / STORAGE_CAPACITY))

    def event_market_cycle(self):
        past_market = list(self.area.past_markets.values())[-1]
        # if energy in this slot was bought: update the storage
        for bought in self.bought_offers[past_market]:
            self.blocked_storage -= bought.energy
            self.used_storage += bought.energy
        # if energy in this slot was sold: update the storage
        for sold in self.sold_offers[past_market]:
            self.used_storage -= sold.energy
        # Check if Storage posted offer in that market that has not been bought
        # If so try to sell the offer again
        if past_market in self.offers_posted.keys():
            for market, offer in list(self.offers_posted.items()):
                if market == past_market:
                    new_selling_price = (
                        # self.offers_posted[market].price is the price we charged including our profit
                        # But self.sell_energy expects a buying price
                        (0.99 - (0.15 * (self.risk / MAX_RISK))) *
                        self.offers_posted[market].price /
                        self.offers_posted[market].energy
                    )
                    self.sell_energy(new_selling_price, self.offers_posted[market].energy)
                    del self.offers_posted[past_market]

    def event_trade(self, *, market, trade):
        # If trade happened: remember it in variable
        if self.owner.name == trade.seller:
            self.sold_offers[market].append(trade.offer)
            self.offers_posted.pop(market, None)

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
                        and min((offer.price / offer.energy), 30) < (avg_cheapest_offer_price * 0.99)
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
        # This ends up in a selling price between 101 and 120 percentage of the buying price
        risk_dependent_selling_price = (
            min_selling_price * (1 + 0.2 * (self.risk / MAX_RISK))
        )
        # Find the most expensive offer out of the list of cheapest offers
        # in currently open markets
        try:
            expensive_offers = list(self.area.cheapest_offers)[-1]
        except IndexError:
            return
        most_expensive_market = expensive_offers.market
        #        self.log.info("risk_dependent_selling_price is %s", risk_dependent_selling_price)
        #        self.log.info("cheapest_price_in_most_expensive_market is %s",
        #                             cheapest_price_in_most_expensive_market)
        # If no energy is passed, try to sell all the Energy left in the storage
        if energy is None:
            energy = self.used_storage
        # Try to create an offer to sell the stored energy

        if energy > 0.0:
            #            # Deleting all old offers
            #            for (market, offer) in self.offers_posted.items():
            #                if market == most_expensive_market:
            #                    try:
            #                        market.delete_offer(offer.id)
            #                    except MarketException:
            #                        return
            # Posting offer with new price
            offer = most_expensive_market.offer(
                energy,
                min(energy * risk_dependent_selling_price, 29.9),
                self.owner.name
            )
            # Updating parameters
            self.used_storage -= self.used_storage
            self.offered_storage += self.used_storage
            self.offers_posted[most_expensive_market] = offer

    def find_avg_cheapest_offers(self):
        # Taking the cheapest offers in every market currently open and building the average
        cheapest_offers = self.area.cheapest_offers
        avg_cheapest_offer_price = (
            sum((offer.price / offer.energy) for offer in cheapest_offers)
            / max(len(cheapest_offers), 1)
        )
        return min(avg_cheapest_offer_price, 30)
