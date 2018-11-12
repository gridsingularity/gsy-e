from d3a.d3a_core.exceptions import MarketException
from d3a.models.state import StorageState
from d3a.models.strategy import BaseStrategy
from d3a.models.const import ConstSettings


class NightStorageStrategy(BaseStrategy):
    parameters = ('risk',)

    def __init__(self, risk=ConstSettings.GeneralSettings.DEFAULT_RISK):
        super().__init__()
        self.risk = risk
        self.state = StorageState(capacity=2 * ConstSettings.StorageSettings.CAPACITY)
        self.selling_price = 30

    def event_tick(self, *, area):
        # Taking the cheapest offers in every market currently open and building the average
        avg_cheapest_offer_price = self.find_avg_cheapest_offers()
        # Check if there are cheap offers to buy
        self.energy_buying_possible(avg_cheapest_offer_price)
        self.state.tick(area)

    def event_market_cycle(self):
        if self.area.past_markets:
            past_market = list(self.area.past_markets.values())[-1]
        else:
            if self.state.used_storage > 0:
                # For the case of the first market slot sell with a default value.
                self.sell_energy(self.selling_price)
            return

        for bought in self.offers.bought_in_market(past_market):
            self.state.fill_blocked_storage(bought.energy)
            self.sell_energy(bought.price, bought.energy)
        # if energy in this slot was sold: update the storage
        for sold in self.offers.sold_in_market(past_market):
            self.state.sold_offered_storage(sold.energy)
        # Check if Storage posted offer in that market that has not been bought
        # If so try to sell the offer again
        self.state.market_cycle(self.area)

        for offer in list(self.offers.open_in_market(past_market)):
            # self.offers_posted[market].price is the price we charged including profit
            # But self.sell_energy expects a buying price
            initial_buying_price = ((offer.price / 1.002) *
                                    (1 /
                                     (1.05 - (0.5 * (self.risk /
                                                     ConstSettings.GeneralSettings.MAX_RISK))
                                      )
                                     )
                                    )
            self.state.remove_offered(offer.energy)
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
                        offer.energy <= self.state.free_storage +
                        ConstSettings.StorageSettings.CAPACITY
                        # Now the storage buys everything cheaper than 29
                        # He will be able to sell this energy during the night
                        and (offer.price / offer.energy) < max(max_buying_price, 29)
                ):
                    # Try to buy the energy
                    try:
                        self.accept_offer(market, offer)
                        self.state.block_storage(offer.energy)
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
            min_selling_price * (1.05 - (0.05 * (self.risk /
                                                 ConstSettings.GeneralSettings.MAX_RISK)))
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
            energy = self.state.used_storage
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
