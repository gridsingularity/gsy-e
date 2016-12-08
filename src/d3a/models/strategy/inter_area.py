from collections import deque
from typing import Dict  # noqa

from d3a.exceptions import MarketException
from d3a.models.events import OfferEvent
from d3a.models.strategy.base import BaseStrategy, log


class InterAreaAgent(BaseStrategy):
    def __init__(self, *, owner, higher_market, lower_market, min_offer_age=1, tick_ratio=4):
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
        self.owner = owner
        self.name = "IAA {}".format(owner.name)
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
        self.offer_age = {}  # type: Dict[str, int]
        # Offer.id lower market -> Offer.id higher market
        self.offered_offers = {}  # type: Dict[str, str]

    @property
    def offered_offers_reverse(self):
        return {v: k for k, v in self.offered_offers.items()}

    def event_tick(self, *, area):
        if area.current_tick % self.tick_ratio != 0:
            return

        for offer in self.markets['higher'].sorted_offers:
            if offer.id not in self.offer_age:
                self.offer_age[offer.id] = area.current_tick
                offer.add_listener(OfferEvent.DELETED, self.event_offer_deleted)
                offer.add_listener(OfferEvent.ACCEPTED, self.event_trade)

        # Find the first offer older than self.min_offer_age and offer it in the lower market
        offered_offers_reverse = self.offered_offers_reverse
        for offer_id, age in list(self.offer_age.items()):
            if offer_id in offered_offers_reverse:
                continue
            if area.current_tick - age < self.min_offer_age:
                continue
            offer = self.markets['higher'].offers.get(offer_id)
            if not offer:
                log.error("Missing offer %s", offer_id)
                continue
            lower_offer = self.markets['lower'].offer(offer.energy, offer.price, self.name)
            lower_offer.add_listener(OfferEvent.ACCEPTED, self.event_trade)
            self.offered_offers[lower_offer.id] = offer_id
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
