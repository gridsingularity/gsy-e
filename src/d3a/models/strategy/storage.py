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
        self.offer_price = 10000

    def event_tick(self, *, area):
        avg_cheapest_offer_price = self.find_avg_cheapest_offers()
        # Here starts the logic if energy should be
        #        self.log.info("self.blocked_storage %s", self.blocked_storage)
        for market in self.area.markets.values():
            for offer in market.sorted_offers:
                if (
                        self.used_storage + self.blocked_storage + offer.energy <= STORAGE_CAPACITY
                        and (offer.price / offer.energy) < avg_cheapest_offer_price
                ):
                    try:
                        self.accept_offer(market, offer)
                        self.blocked_storage += offer.energy
                        self.done_trades[market].append(offer)
                    except MarketException:
                        # Offer already gone etc., try next one.
                        continue
                        # TODO check if posted offers are still the cheapest

    def event_market_cycle(self):
        # Update the energy balances
        past_market = list(self.area.past_markets.values())[-1]
        avg_cheapest_offer_price = self.find_avg_cheapest_offers()
        # Maximum selling price using the highest risk is 20% above the average price
        max_selling_price = 0.2 * avg_cheapest_offer_price
        # formula to calculate a profitable selling price
        selling_price = avg_cheapest_offer_price + ((self.risk / 100) * max_selling_price)
        # if energy for this slot was bought: sell it in the most expensive market
        for bought in self.done_trades[past_market]:
            self.blocked_storage -= bought.energy
            self.used_storage += bought.energy
        expensive_offers = list(self.area.cheapest_offers)[-1]
        # Finding the most expensive market
        market = expensive_offers.market
        # Post offer in most expensive market
        #        self.log.info("selling_price %s", selling_price)
        #        self.log.info("max_selling_price %s", max_selling_price)
        self.log.info("selling_price %s", selling_price)
        self.log.info("list(market.sorted_offers)[0].price %s",
                      list(market.sorted_offers)[0].price)
        self.log.info("self.used_storage  %s", self.used_storage)
        if (
            selling_price < list(market.sorted_offers)[0].price and
            self.used_storage > 0 and
            # if selling price cheaper than the price of currently existing offer
            selling_price < self.offer_price
        ):
            # TODO Here we need to delete the old offers to prevent trying to spend the energy
            # several times
            offer = market.offer(
                self.used_storage,
                selling_price,
                self.owner.name
            )
            self.offers_posted[offer.id] = market
            self.offer_price = offer.price

    def event_trade(self, *, market, trade):
        if self.owner.name == trade.seller:
            self.used_storage -= trade.offer.energy
            # TODO post information about earned money

    def find_avg_cheapest_offers(self):
        cheapest_offers = self.area.cheapest_offers
        avg_cheapest_offer_price = (
            sum(offer.price for offer in cheapest_offers)
            / max(len(cheapest_offers), 1)
        )
        return avg_cheapest_offer_price
