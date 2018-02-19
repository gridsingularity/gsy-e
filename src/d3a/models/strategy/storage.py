from d3a.exceptions import MarketException
from d3a.models.state import StorageState
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import DEFAULT_RISK, MAX_RISK


class StorageStrategy(BaseStrategy):
    parameters = ('risk',)

    def __init__(self, risk=DEFAULT_RISK, initial_capacity=0.0):
        super().__init__()
        self.risk = risk
        self.state = StorageState(initial_capacity=initial_capacity, loss_per_hour=0.0)
        self.selling_price = 30

    def event_tick(self, *, area):
        # Taking the cheapest offers in every market currently open and building the average
        # avg_cheapest_offer_price = self.find_avg_cheapest_offers()
        most_expensive_offer_price = self.find_most_expensive_market_price()
        # Check if there are cheap offers to buy
        self.buy_energy(most_expensive_offer_price)
        self.state.tick(area)

    def event_market_cycle(self):
        past_market = list(self.area.past_markets.values())[-1]
        # if energy in this slot was bought: update the storage
        for bought in self.offers.bought_in_market(past_market):
            self.state.fill_blocked_storage(bought.energy)
            self.sell_energy(buying_price=(bought.price / bought.energy), energy=bought.energy)
        # if energy in this slot was sold: update the storage
        for sold in self.offers.sold_in_market(past_market):
            self.state.sold_offered_storage(sold.energy)
        # Check if Storage posted offer in that market that has not been bought
        # If so try to sell the offer again
        for offer in self.offers.open_in_market(past_market):
            # self.offers_posted[market].price is the price we charged including profit
            # But self.sell_energy expects a buying price
            offer_price = (offer.price / offer.energy)

            initial_buying_price = (
                                        (offer_price / 1.01) *
                                        (1 / (1.1 - (0.1 * (self.risk / MAX_RISK))))
                                    )
            self.sell_energy(initial_buying_price, offer.energy, open_offer=True)
            self.offers.sold_offer(offer.id, past_market)
        self.state.market_cycle(self.area)

    def buy_energy(self, avg_cheapest_offer_price):
        # Here starts the logic if energy should be bought
        # Iterating over all offers in every open market
        for market in self.area.markets.values():
            for offer in market.sorted_offers:
                if offer.seller == self.owner.name:
                    # Don't buy our own offer
                    continue
                # Check if storage has free capacity and if the price is cheap enough
                if (self.state.free_storage >= offer.energy
                        and (offer.price / offer.energy) < (avg_cheapest_offer_price * 0.99)):
                    # Try to buy the energy
                    try:
                        self.accept_offer(market, offer)
                        self.state.block_storage(offer.energy)
                        return True
                    except MarketException:
                        # Offer already gone etc., try next one.
                        return False
                else:
                    return False

    def sell_energy(self, buying_price, energy=None, open_offer=False):
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
            energy = self.state.used_storage
        # Try to create an offer to sell the stored energy

        if energy > 0.0:
            offer = most_expensive_market.offer(
                energy * min(risk_dependent_selling_price, 29.9),
                energy,
                self.owner.name
            )
            # Updating parameters
            if not open_offer:
                self.state.offer_storage(energy)
            self.offers.post(offer, most_expensive_market)

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
