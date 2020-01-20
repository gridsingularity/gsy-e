"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from typing import Union, List  # noqa
from d3a.events.event_structures import MarketEvent, AreaEvent


class EventMixin:

    def _event_mapping(self, event):
        if event == AreaEvent.TICK:
            return self.event_tick
        elif event == AreaEvent.MARKET_CYCLE:
            return self.event_market_cycle
        elif event == AreaEvent.BALANCING_MARKET_CYCLE:
            return self.event_balancing_market_cycle
        elif event == AreaEvent.ACTIVATE:
            return self.event_activate
        elif event == MarketEvent.OFFER:
            return self.event_offer
        elif event == MarketEvent.OFFER_SPLIT:
            return self.event_offer_split
        elif event == MarketEvent.OFFER_DELETED:
            return self.event_offer_deleted
        elif event == MarketEvent.TRADE:
            return self.event_trade
        elif event == MarketEvent.BID_TRADED:
            return self.event_bid_traded
        elif event == MarketEvent.BID_DELETED:
            return self.event_bid_deleted
        elif event == MarketEvent.BID_CHANGED:
            return self.event_bid_changed
        elif event == MarketEvent.BALANCING_OFFER:
            return self.event_balancing_offer
        elif event == MarketEvent.BALANCING_OFFER_SPLIT:
            return self.event_balancing_offer_split
        elif event == MarketEvent.BALANCING_OFFER_DELETED:
            return self.event_balancing_offer_deleted
        elif event == MarketEvent.BALANCING_TRADE:
            return self.event_balancing_trade

    def event_listener(self, event_type: Union[AreaEvent, MarketEvent], **kwargs):
        self.log.trace("Dispatching event %s", event_type.name)
        self._event_mapping(event_type)(**kwargs)

    def event_tick(self):
        pass

    def event_market_cycle(self):
        pass

    def event_balancing_market_cycle(self):
        pass

    def event_activate(self):
        pass

    def event_offer(self, *, market_id, offer):
        pass

    def event_offer_split(self, *, market_id, original_offer, accepted_offer, residual_offer):
        pass

    def event_offer_deleted(self, *, market_id, offer):
        pass

    def event_trade(self, *, market_id, trade):
        pass

    def event_bid_traded(self, *, market_id, bid_trade):
        pass

    def event_bid_deleted(self, *, market_id, bid):
        pass

    def event_bid_changed(self, *, market_id, existing_bid, new_bid):
        pass

    def event_balancing_offer(self, *, market_id, offer):
        pass

    def event_balancing_offer_split(self, *, market_id, original_offer, accepted_offer,
                                    residual_offer):
        pass

    def event_balancing_offer_deleted(self, *, market_id, offer):
        pass

    def event_balancing_trade(self, *, market_id, trade):
        pass
