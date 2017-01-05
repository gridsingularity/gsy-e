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
        self.buought_offers = defaultdict(list)  # type: Dict[Market, List[Offer]]
        self.sold_offers = defaultdict(list)  # type: Dict[Market, List[Trade]]
        self.used_storage = 0.00
        self.blocked_storage = 0.00
        self.selling_price = 30

    def event_tick(self, *, area):
        # Taking the cheapest offers in every market currently open and building the average
        avg_cheapest_offer_price = self.find_avg_cheapest_offers()
        # Here starts the logic if energy should be bought
        # Iterating over all offers in every open market
        for market in self.area.markets.values():
            for offer in market.sorted_offers:
                # Check if storage has free capacity and if the price is cheap enough
                if (
                        self.used_storage + self.blocked_storage + offer.energy <= STORAGE_CAPACITY
                        and (offer.price / offer.energy) <= avg_cheapest_offer_price
                ):
                    # Try to buy the energy
                    try:
                        self.accept_offer(market, offer)
                        self.blocked_storage += offer.energy
                        self.buought_offers[market].append(offer)
                    except MarketException:
                        # Offer already gone etc., try next one.
                        continue
        # Check if any energy from the storage can be sold
        self.sell_energy()

    def event_market_cycle(self):
        past_market = list(self.area.past_markets.values())[-1]
        # if energy in this slot was bought: update the storage
        for bought in self.buought_offers[past_market]:
            self.blocked_storage -= bought.energy
            self.used_storage += bought.energy
        # if energy in this slot was sold: update the storage
        for sold in self.sold_offers[past_market]:
            self.used_storage -= sold.energy
        # Check if any energy from the storage can be sold now
        self.sell_energy()

    def event_trade(self, *, market, trade):
        # If trade happened: remember it in variable
        if self.owner.name == trade.seller:
            self.sold_offers[market].append(trade.offer)
            # TODO post information about earned money

    def sell_energy(self):
        # Taking the cheapest offers in every market currently open and building the average
        avg_cheapest_offer_price = self.find_avg_cheapest_offers()
        # Highest risk selling price using the highest risk is 20% above the average price
        max_selling_price = 0.2 * avg_cheapest_offer_price
        # Formula to calculate a profitable selling price
        current_selling_price = avg_cheapest_offer_price + ((self.risk / 100) * max_selling_price)
        # Find the most expensive offer out of the list of cheapest offers
        # in currently open markets
        try:
            expensive_offers = list(self.area.cheapest_offers)[-1]
        except IndexError:
            return
        market = expensive_offers.market
        # sorted_offer_price is the price of the offer expensive_offers
        sorted_offer_price = (
            list(market.sorted_offers)[0].price /
            list(market.sorted_offers)[0].energy
        )
        # Post offer in most expensive market, if strategy price is cheap enough
        if (
                current_selling_price <= sorted_offer_price and
                self.used_storage > 0 and
                current_selling_price < self.selling_price
        ):
            # Deleting all old offers
            for (market, offer_id) in self.offers_posted:
                    market.delete_offer(offer_id)
            # Posting offer with new price
            offer = market.offer(
                self.used_storage,
                current_selling_price * self.used_storage,
                self.owner.name
            )
            # Updating parameters
            self.selling_price = current_selling_price
            self.offers_posted[offer.id] = market

    def find_avg_cheapest_offers(self):
        # Taking the cheapest offers in every market currently open and building the average
        cheapest_offers = self.area.cheapest_offers
        avg_cheapest_offer_price = (
            sum((offer.price / offer.energy) for offer in cheapest_offers)
            / max(len(cheapest_offers), 1)
        )
        return avg_cheapest_offer_price
