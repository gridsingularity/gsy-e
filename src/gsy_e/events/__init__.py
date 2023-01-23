"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
from gsy_e.events.event_structures import MarketEvent, AreaEvent


class EventMixin:
    """Mixin class that injects event handling behavior on the strategy classes."""
    def _event_mapping(self, event):
        # pylint: disable=too-many-return-statements,too-many-branches
        if event == AreaEvent.TICK:
            return self.event_tick
        if event == AreaEvent.MARKET_CYCLE:
            return self.event_market_cycle
        if event == AreaEvent.BALANCING_MARKET_CYCLE:
            return self.event_balancing_market_cycle
        if event == AreaEvent.ACTIVATE:
            return self.event_activate
        if event == MarketEvent.OFFER:
            return self.event_offer
        if event == MarketEvent.OFFER_SPLIT:
            return self.event_offer_split
        if event == MarketEvent.OFFER_DELETED:
            return self.event_offer_deleted
        if event == MarketEvent.OFFER_TRADED:
            return self.event_offer_traded
        if event == MarketEvent.BID:
            return self.event_bid
        if event == MarketEvent.BID_TRADED:
            return self.event_bid_traded
        if event == MarketEvent.BID_DELETED:
            return self.event_bid_deleted
        if event == MarketEvent.BID_SPLIT:
            return self.event_bid_split
        if event == MarketEvent.BALANCING_OFFER:
            return self.event_balancing_offer
        if event == MarketEvent.BALANCING_OFFER_SPLIT:
            return self.event_balancing_offer_split
        if event == MarketEvent.BALANCING_OFFER_DELETED:
            return self.event_balancing_offer_deleted
        if event == MarketEvent.BALANCING_TRADE:
            return self.event_balancing_trade
        assert False, f"No event {event}."

    def event_listener(self, event_type: Union[AreaEvent, MarketEvent], **kwargs):
        """
        Listen to emitted events and dispatch them to the appropriate method according to the
        event type.
        """
        self.log.trace("Dispatching event %s", event_type.name)
        self._event_mapping(event_type)(**kwargs)

    def event_tick(self):
        """Event emitted on every new tick on the simulation."""

    def event_market_cycle(self):
        """Event emitted on every new market cycle on the simulation."""

    def event_balancing_market_cycle(self):
        """Event emitted on every new balancing market cycle on the simulation."""

    def event_activate(self, **kwargs):
        """Event emitted during the simulation activation."""

    def event_offer(self, *, market_id, offer):
        """Event emitted when a new offer is posted."""

    def event_offer_split(self, *, market_id, original_offer, accepted_offer, residual_offer):
        """Event emitted if an offer is split to an accepted and a residual one."""

    def event_offer_deleted(self, *, market_id, offer):
        """Event emitted if an offer is deleted."""

    def event_offer_traded(self, *, market_id, trade):
        """Method triggered by the MarketEvent.OFFER_TRADED event."""

    def event_bid(self, *, market_id, bid):
        """Event emitted when a new bid is posted."""

    def event_bid_traded(self, *, market_id, bid_trade):
        """Method triggered by the MarketEvent.BID_TRADED event."""

    def event_bid_deleted(self, *, market_id, bid):
        """Event emitted when a bid is deleted."""

    def event_bid_split(self, *, market_id, original_bid, accepted_bid, residual_bid):
        """Event emitted when a bid is split into an accepted and a residual one."""

    def event_balancing_offer(self, *, market_id, offer):
        """Event emitted when a new balancing offer is posted."""

    def event_balancing_offer_split(self, *, market_id, original_offer, accepted_offer,
                                    residual_offer):
        """Event emitted when a balancing offer is split."""

    def event_balancing_offer_deleted(self, *, market_id, offer):
        """Event emitted when a balancing offer is deleted."""

    def event_balancing_trade(self, *, market_id, trade):
        """Event emitted when a balancing trade is created."""
