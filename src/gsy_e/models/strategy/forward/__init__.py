from abc import ABC, abstractmethod
from typing import Union

from gsy_e.events import EventMixin, AreaEvent, MarketEvent
from gsy_e.models.base import AreaBehaviorBase


class ForwardStrategyBase(EventMixin, AreaBehaviorBase, ABC):
    """Base class for the forward market strategies."""
    def __init__(self):
        super().__init__()
        self.enabled = True
        self._allowed_disable_events = [
            AreaEvent.ACTIVATE, MarketEvent.OFFER_TRADED, MarketEvent.BID_TRADED]

    @abstractmethod
    def update_open_orders(self):
        """Update the open orders on the forward markets."""
        raise NotImplementedError

    @abstractmethod
    def post_orders_to_new_markets(self):
        """Post orders to markets that just opened."""
        raise NotImplementedError

    def event_listener(self, event_type: Union[AreaEvent, MarketEvent], **kwargs):
        """Dispatches the events received by the strategy to the respective methods."""
        if self.enabled or event_type in self._allowed_disable_events:
            super().event_listener(event_type, **kwargs)

    def event_offer_traded(self, *, market_id, trade):
        """Method triggered by the MarketEvent.OFFER_TRADED event."""

    def event_bid_traded(self, *, market_id, bid_trade):
        """Method triggered by the MarketEvent.BID_TRADED event."""

    def event_tick(self):
        self.update_open_orders()

    def event_market_cycle(self):
        self.post_orders_to_new_markets()
