# from d3a.exceptions import MarketException
from collections import defaultdict

from d3a.models.strategy.base import BaseStrategy
from d3a.exceptions import MarketException
from d3a.models.strategy.const import DEFAULT_RISK, STORAGE_CAPACITY


class StorageStrategy(BaseStrategy):
    def __init__(self, risk=DEFAULT_RISK):
        super().__init__()
        self.risk = risk
        self.offers_posted = {}  # type: Dict[str, Market]
        self.done_trades = defaultdict(list)  # type: Dict[Market, List[Offer]]
        self.used_storage = 0
        self.blocked_storage = 0

    def event_tick(self, *, area):
        cheapest_offers = self.area.cheapest_offers
        avg_cheapest_offer_price = (
            sum(offer.price for offer in cheapest_offers)
            / len(cheapest_offers)
        )
        # Here starts the logic if energy should be bought
        for market in self.area.markets.values():
            for offer in market.sorted_offers:
                if (
                        self.used_storage + self.blocked_storage < STORAGE_CAPACITY and
                        offer.price < avg_cheapest_offer_price
                ):
                    try:
                        market.accept_offer(offer, self.owner.name)
                        self.log.debug("Buying %s", offer)
                        self.blocked_storage += offer.energy
                        self.done_trades[market].append(offer)
                    except MarketException:
                        # Offer already gone etc., try next one.
                        continue
                        # TODO check if posted offers are still the cheapes

    def event_market_cycle(self):
        # Update the energy balances
        past_market = self.area.past_markets.values()[0]
        for offer in self.done_trades[past_market]:
            self.blocked_storage -= offer.energy
            self.used_storage += offer.energy
