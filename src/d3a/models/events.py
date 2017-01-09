from enum import Enum
from typing import Union


class OfferEvent(Enum):
    DELETED = 1
    ACCEPTED = 2


class MarketEvent(Enum):
    OFFER = 1
    OFFER_CHANGED = 4
    OFFER_DELETED = 2
    TRADE = 3


class AreaEvent(Enum):
    TICK = 1
    MARKET_CYCLE = 2
    ACTIVATE = 3


class EventMixin:
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

    def event_offer_changed(self, *, market, existing_offer, new_offer):
        pass

    def event_offer_deleted(self, *, market, offer):
        pass

    def event_trade(self, *, market, trade):
        pass
