import random
from collections import deque
from logging import getLogger
from typing import Dict, Union  # noqa

from cached_property import cached_property
from d3a.exceptions import MarketException
from d3a.models.events import AreaEvent, MarketEvent, OfferEvent  # noqa
from d3a.models.market import Market  # noqa
from d3a.util import TaggedLogWrapper


log = getLogger(__name__)


class BaseStrategy:
    def __init__(self):
        self.area = None

    @property
    def log(self):
        if not self.area:
            log.warning("Logging without area in %s, using default logger",
                        self.__class__.__name__, stack_info=True)
            return log
        return self._log

    @cached_property
    def _log(self):
        return TaggedLogWrapper(log, "{s.area.name}:{s.__class__.__name__}".format(s=self))

    def event_listener(self, event_type: Union[AreaEvent, MarketEvent], **kwargs):
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

    def event_tick(self, *, area):
        if random.random() <= self.buy_chance:
            time, market = random.choice(list(area.markets.items()))
            for offer in market.sorted_offers:
                try:
                    market.accept_offer(offer, self.area.name)
                    self.log.info("Buying %s", offer)
                    break
                except MarketException:
                    # Offer already gone etc., use next one.
                    continue
        # Report consumption


class OfferStrategy(BaseStrategy):
    def __init__(self, *, offer_chance=0.01, energy_range=(2, 10), price_fraction_choice=(3, 4)):
        super().__init__()
        self.offer_chance = offer_chance
        self.energy_range = energy_range
        self.price_fraction = price_fraction_choice

    def event_tick(self, *, area):
        if random.random() <= self.offer_chance:
            energy = random.randint(*self.energy_range)
            time, market = random.choice(list(area.markets.items()))
            offer = market.offer(
                energy,
                energy / random.choice(self.price_fraction),
                self.area.name
            )
            self.log.info("Offering %s @ %s", offer, time.strftime('%H:%M'))


class InterAreaAgent(BaseStrategy):
    def __init__(self, *, area, higher_market, lower_market, min_offer_age=1, tick_ratio=4):
        """
        Equalize markets

        :param higher_market:
        :type higher_market: Market
        :param lower_market:
        :type lower_market: Market
        :param tick_ratio: How often markets should be compared (default 4 := 1/4)
        :type tick_ratio: int
        """
        super().__init__()
        self.area = area
        self.name = "IAA {}".format(area.name)
        self.markets = {
            'lower': lower_market,
            'higher': higher_market,
        }
        self.min_offer_age = min_offer_age
        self.tick_ratio = tick_ratio
        self.last_avg_prices = {
            'lower': deque(maxlen=5),
            'higher': deque(maxlen=5)
        }
        self.tick_counter = 0
        self.offer_age = {}  # type: Dict[str, int]
        # Offer.id lower market -> Offer.id higher market
        self.offered_offers = {}  # type: Dict[str, str]

    @property
    def offered_offers_reverse(self):
        return {v: k for k, v in self.offered_offers.items()}

    def event_tick(self, *, area):
        self.tick_counter += 1
        if self.tick_counter % self.tick_ratio != 0:
            return

        for offer in self.markets['higher'].sorted_offers:
            if offer.id not in self.offer_age:
                self.offer_age[offer.id] = self.tick_counter
                offer.add_listener(OfferEvent.DELETED, self.event_offer_deleted)
                offer.add_listener(OfferEvent.ACCEPTED, self.event_trade)

        # Find the first offer older than self.min_offer_age and offer it in the lower market
        for offer_id, age in list(self.offer_age.items()):
            if self.tick_counter - age < self.min_offer_age:
                continue
            offer = self.markets['higher'].offers.get(offer_id)
            if not offer:
                log.error("Missing offer %s", offer_id)
                continue
            lower_offer = self.markets['lower'].offer(offer.energy, offer.price, self.name)
            lower_offer.add_listener(OfferEvent.ACCEPTED, self.event_trade)
            self.offered_offers[lower_offer.id] = offer_id
            del self.offer_age[offer_id]
            self.log.info("Offering %s", lower_offer)

    def event_trade(self, *, market, trade, offer=None):
        if trade.offer.id in self.offer_age:
            # Someone else bought an offer we're watching - remove
            del self.offer_age[trade.offer.id]

        if trade.offer.id in self.offered_offers:
            # Offer was accepted in lower market - buy in higher
            trade_lower = self.markets['higher'].accept_offer(self.offered_offers[trade.offer.id],
                                                              self.name)
            self.log.info("Offer accepted %s", trade_lower)

        offered_offers_reverse = self.offered_offers_reverse
        if trade.offer.id in offered_offers_reverse:
            # Offer from the higher market we offered in the lower market was bought
            # by someone else in the higher market - delete offer in lower market
            try:
                self.markets['lower'].delete_offer(offered_offers_reverse[trade.offer.id])
            except MarketException:
                self.log.exception("Error deleting InterAreaAgent offer")
            del self.offered_offers[offered_offers_reverse[trade.offer.id]]

    def event_offer_deleted(self, *, market, offer):
        if offer.id in self.offer_age:
            # Source offer we're watching in higher market was deleted - remove
            self.offer_age.pop(offer.id, None)
        offered_offers_reverse = self.offered_offers_reverse
        if offer.id in offered_offers_reverse:
            # Source offer in higher market of an offer we're already offering in the lower market
            # was deleted - also delete in lower market
            try:
                self.markets['lower'].delete_offer(offered_offers_reverse[offer.id])
            except MarketException:
                self.log.exception("Error deleting InterAreaAgent offer")
            del self.offered_offers[offered_offers_reverse[offer.id]]
