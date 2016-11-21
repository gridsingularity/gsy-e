import random
from logging import getLogger

from cached_property import cached_property

from d3a.util import TaggedLogWrapper

log = getLogger(__name__)


class BaseStrategy:
    def __init__(self):
        self.area = None

    @property
    def log(self):
        if not self.area:
            log.warning("Logging without area, using default logger")
            return log
        return self._log

    @cached_property
    def _log(self):
        return TaggedLogWrapper(log, "{s.area.name}:{s.__class__.__name__}".format(s=self))

    def event_listener(self, event_type, **kwargs):
        self.log.debug("Dispatching event %s", event_type.name)
        getattr(self, "event_{}".format(event_type.name.lower()))(**kwargs)

    def event_tick(self, *, area):
        pass

    def event_market_cycle(self):
        pass

    def event_activate(self):
        pass

    def event_offer(self, *, market, offer):
        pass

    def event_offer_deleted(self, *, market, offer):
        pass

    def event_trade(self, *, market, trade):
        pass


class BuyStrategy(BaseStrategy):
    def __init__(self, *, buy_chance=0.1):
        super().__init__()
        self.buy_chance = buy_chance

    def event_offer(self, *, market, offer):
        if random.random() <= self.buy_chance:
            market.accept_offer(offer, self.area.name)
            self.log.info("Buying %s", offer)


class OfferStrategy(BaseStrategy):
    def __init__(self, *, offer_chance=0.01):
        super().__init__()
        self.offer_chance = offer_chance

    def event_tick(self, *, area):
        if random.random() <= self.offer_chance:
            energy = random.randint(2, 10)
            time, market = random.choice(list(area.markets.items()))
            offer = market.offer(
                energy,
                energy // 3,
                self.area.name
            )
            self.log.info("Offering %s @ %s", offer, time.strftime('%H:%M'))
