# from d3a.exceptions import MarketException
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import DEFAULT_RISK, STORAGE_CAPACITY


class StorageStrategy(BaseStrategy):
    def __init__(self, risk=DEFAULT_RISK):
        super().__init__()
        self.risk = risk
        self.offers_posted = {}  # type: Dict[str, Market]
        self.used_storage = 0

    def event_tick(self, *, area):
        for market in self.area.markets.values():
            min_price = market.min_trade_price
            #            max_price = market.max_trade_price
            buying_threshold = (self.area.market_prices.avg_offer_price() -
                                (0.15 - self.risk / 1000) *
                                self.area.market_prices.avg_offer_price()
                                )
            if (
                            self.used_storage < STORAGE_CAPACITY and
                            min_price < buying_threshold
            ):
                pass

# try:
#                    self.area.market.market_prices.accept_offer(offer, self.area.name)
#                    self.log.debug("Buying %s", offer)
#                    # TODO: Set realistic temperature change
#                except MarketException:
#                    # Offer already gone etc., try next one.
#                    continue
