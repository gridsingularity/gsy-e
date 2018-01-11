from d3a.exceptions import MarketException
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import DEFAULT_RISK, STORAGE_CAPACITY, MAX_RISK


class NightStorageStrategy(BaseStrategy):
    parameters = ('risk',)

    def __init__(self, risk=DEFAULT_RISK):
        super().__init__()
        self.risk = risk
        self.used_storage = 0.00
        self.offered_storage = 0.00
        self.blocked_storage = 0.00
        self.selling_price = 30

    def event_tick(self, *, area):
        # The storage looses 1% of capacity per hour
        self.used_storage *= (1 - ((0.01 * self.area.config.tick_length.total_seconds())
                                   / (60 * 60)
                                   )
                              )
        # Taking the cheapest offers in every market currently open and building the average
        avg_cheapest_offer_price = self.find_avg_cheapest_offers()
        # Check if there are cheap offers to buy
        self.energy_buying_possible(avg_cheapest_offer_price)

        if self.used_storage > (0.8 * 2 * STORAGE_CAPACITY):
            self.log.info("Storage reached more than 80% Battery: %s", (self.used_storage
                                                                        / (2 * STORAGE_CAPACITY)))

    def event_market_cycle(self):
        past_market = list(self.area.past_markets.values())[-1]
        # if energy in this slot was bought: update the storage & try to sell it
        for bought_id in self.offers.bought_in_market(past_market):
            bought = past_market.offers[bought_id]
            self.blocked_storage -= bought.energy
            self.used_storage += bought.energy
            self.sell_energy(bought.price, bought.energy)
        # if energy in this slot was sold: update the storage
        for sold_id in self.offers.sold_in_market(past_market):
            sold = past_market.offers[sold_id]
            self.offered_storage -= sold.energy
        # Check if Storage posted offer in that market that has not been bought
        # If so try to sell the offer again

        for offer_id in list(self.offers.posted_in_market(past_market)):
            offer = past_market.offers[offer_id]
            # self.offers_posted[market].price is the price we charged including profit
            # But self.sell_energy expects a buying price
            initial_buying_price = ((offer.price / 1.002) *
                                    (1 /
                                     (1.05 - (0.5 * (self.risk / MAX_RISK))
                                      )
                                     )
                                    )
            self.offered_storage -= offer.energy
            self.used_storage += offer.energy
            self.sell_energy(initial_buying_price, offer.energy)

    def energy_buying_possible(self, max_buying_price):
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
                             + self.offered_storage <= STORAGE_CAPACITY * 2
                             )
                        # Now the storage buys everything cheaper than 29
                        # He will be able to sell this energy during the night
                        and (offer.price / offer.energy) < max(max_buying_price, 29)
                ):
                    # Try to buy the energy
                    try:
                        self.accept_offer(market, offer)
                        self.blocked_storage += offer.energy
                        self.offers.bought[offer.id] = market
                        continue
                    except MarketException:
                        # Offer already gone etc., try next one.
                        continue
                else:
                    continue

    def sell_energy(self, buying_price, energy=None):
        # Highest risk selling price using the highest risk is 20% above the average price
        min_selling_price = 1.05 * buying_price
        # This ends up in a selling price between 101 and 105 percentage of the buying price
        risk_dependent_selling_price = (
            min_selling_price * (1.05 - (0.05 * (self.risk / MAX_RISK)))
        )
        # Find the most expensive offer out of the list of cheapest offers
        # in currently open markets
        try:
            expensive_offers = list(self.area.cheapest_offers)[-1]
        except IndexError:
            return
        most_expensive_market = expensive_offers.market
        # If no energy is passed, try to sell all the Energy left in the storage
        if energy <= 0 or energy is None:
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
                energy * min(risk_dependent_selling_price, 29.9),
                energy,
                self.owner.name
            )
            # Updating parameters
            self.used_storage -= energy
            self.offered_storage += energy
            self.offers.post(offer.id, most_expensive_market)

    def find_avg_cheapest_offers(self):
        # Taking the cheapest offers in every market currently open and building the average
        cheapest_offers = self.area.cheapest_offers
        avg_cheapest_offer_price = (
            sum((offer.price / offer.energy) for offer in cheapest_offers)
            / max(len(cheapest_offers), 1)
        )
        return min(avg_cheapest_offer_price, 30)
