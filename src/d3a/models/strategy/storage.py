from collections import defaultdict
from typing import Dict, List  # noqa

from d3a.models.market import Market, Offer  # noqa
from d3a.models.strategy.base import BaseStrategy
from d3a.exceptions import MarketException
from d3a.models.strategy.const import DEFAULT_RISK, STORAGE_CAPACITY


class StorageStrategy(BaseStrategy):
    def __init__(self, risk=DEFAULT_RISK):
        super().__init__()
        self.risk = risk
        self.offers_posted = {}  # type: Dict[str, Market]
        self.done_trades = defaultdict(list)  # type: Dict[Market, List[Offer]]
        self.used_storage = 0.00
        self.blocked_storage = 0.00
        self.selling_price = 30

    def event_tick(self, *, area):
        avg_cheapest_offer_price = self.find_avg_cheapest_offers()
        # Here starts the logic if energy should be
        #        self.log.info("self.blocked_storage %s", self.blocked_storage)
        for market in self.area.markets.values():
            for offer in market.sorted_offers:
                if (
                        self.used_storage + self.blocked_storage + offer.energy <= STORAGE_CAPACITY
                        and (offer.price / offer.energy) <= avg_cheapest_offer_price
                ):
                    try:
                        self.accept_offer(market, offer)
                        self.blocked_storage += offer.energy
                        self.done_trades[market].append(offer)
                    except MarketException:
                        # Offer already gone etc., try next one.
                        continue
                # TODO exit all of the loops correctly
                # TODO - why isn't the event_tick code executed every tick properly?
        self.sell_energy()

    def event_market_cycle(self):
        # Update the energy balances
        past_market = list(self.area.past_markets.values())[-1]
        # if energy for this slot was bought: sell it in the most expensive market
        for bought in self.done_trades[past_market]:
            self.blocked_storage -= bought.energy
            self.used_storage += bought.energy
        self.sell_energy()

    def event_trade(self, *, market, trade):
        if self.owner.name == trade.seller:
            self.used_storage -= trade.offer.energy
            # TODO post information about earned money

    def sell_energy(self):
        avg_cheapest_offer_price = self.find_avg_cheapest_offers()
        # Maximum selling price using the highest risk is 20% above the average price
        max_selling_price = 0.2 * avg_cheapest_offer_price
        # formula to calculate a profitable selling price
        new_selling_price = avg_cheapest_offer_price + ((self.risk / 100) * max_selling_price)
        try:
            expensive_offers = list(self.area.cheapest_offers)[-1]
        except IndexError:
            return
        # Finding the most expensive market
        market = expensive_offers.market
        sorted_offer_price = (
            list(market.sorted_offers)[0].price /
            list(market.sorted_offers)[0].energy
        )
        # Post offer in most expensive market
#        self.log.info("new_selling_price %s", new_selling_price)
#        self.log.info("sorted_offer_price %s", sorted_offer_price)
#        self.log.info("self.selling_price %s", self.selling_price)
        if (
                new_selling_price <= sorted_offer_price and
                self.used_storage > 0 and
                new_selling_price < self.selling_price
        ):
            # TODO Here we need to delete the old offers to prevent trying to spend the energy
            # several times
            # Deleting all old offers
            for (market, offer_id) in self.offers_posted:
                    market.delete_offer(offer_id)
            # Posting offer with new information
            offer = market.offer(
                self.used_storage,
                new_selling_price * self.used_storage,
                self.owner.name
            )
            # Updating parameters
            self.selling_price = new_selling_price
            self.offers_posted[offer.id] = market

    def find_avg_cheapest_offers(self):
        cheapest_offers = self.area.cheapest_offers
        avg_cheapest_offer_price = (
            sum((offer.price / offer.energy) for offer in cheapest_offers)
            / max(len(cheapest_offers), 1)
        )
        return avg_cheapest_offer_price
