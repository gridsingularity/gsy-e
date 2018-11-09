from typing import Union, List  # noqa
from d3a.events.event_structures import MarketEvent, AreaEvent


class EventMixin:

    @property
    def _event_mapping(self):
        try:
            return self._event_map
        except AttributeError:
            self._event_map = {
                AreaEvent.TICK: self.event_tick,
                AreaEvent.MARKET_CYCLE: self.event_market_cycle,
                AreaEvent.BALANCING_MARKET_CYCLE: self.event_balancing_market_cycle,
                AreaEvent.ACTIVATE: self.event_activate,
                MarketEvent.OFFER: self.event_offer,
                MarketEvent.OFFER_CHANGED: self.event_offer_changed,
                MarketEvent.OFFER_DELETED: self.event_offer_deleted,
                MarketEvent.TRADE: self.event_trade,
                MarketEvent.BID_TRADED: self.event_bid_traded,
                MarketEvent.BID_DELETED: self.event_bid_deleted,
                MarketEvent.BALANCING_OFFER: self.event_balancing_offer,
                MarketEvent.BALANCING_OFFER_CHANGED: self.event_balancing_offer_changed,
                MarketEvent.BALANCING_OFFER_DELETED: self.event_balancing_offer_deleted,
                MarketEvent.BALANCING_TRADE: self.event_balancing_trade
            }
            return self._event_map

    def event_listener(self, event_type: Union[AreaEvent, MarketEvent], **kwargs):
        self.log.debug("Dispatching event %s", event_type.name)
        self._event_mapping[event_type](**kwargs)

    def event_tick(self, *, area):
        pass

    def event_market_cycle(self):
        pass

    def event_balancing_market_cycle(self):
        pass

    def event_activate(self):
        pass

    def event_offer(self, *, market_id, offer):
        pass

    def event_offer_changed(self, *, market_id, existing_offer, new_offer):
        pass

    def event_offer_deleted(self, *, market_id, offer):
        pass

    def event_trade(self, *, market_id, trade):
        pass

    def event_bid_traded(self, *, market_id, bid_trade):
        pass

    def event_bid_deleted(self, *, market_id, bid):
        pass

    def event_balancing_offer(self, *, market_id, offer):
        pass

    def event_balancing_offer_changed(self, *, market_id, existing_offer, new_offer):
        pass

    def event_balancing_offer_deleted(self, *, market_id, offer):
        pass

    def event_balancing_trade(self, *, market_id, trade):
        pass
