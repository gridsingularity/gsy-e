from collections import defaultdict
from logging import getLogger
from typing import Set, List, Dict, Any, Union  # noqa

from d3a.exceptions import SimulationException
from d3a.models.base import AreaBehaviorBase
from d3a.models.events import EventMixin, TriggerMixin, Trigger, AreaEvent, MarketEvent
from d3a.models.market import Market, Offer  # noqa


log = getLogger(__name__)


class _TradeLookerUpper:
    def __init__(self, owner_name):
        self.owner_name = owner_name

    def __getitem__(self, market):
        for trade in market.trades:
            owner_name = self.owner_name
            if trade.seller == owner_name or trade.buyer == owner_name:
                yield trade


class Offers:
    """
    Keep track of a strategy's accepted and own offers.

    When writing a strategy class, use the post(), remove() and
    replace() methods to keep track of offers.

    posted_in_market() yields all offers that have been posted,
    open_in_market() only those who have not been sold.
    """

    def __init__(self, strategy):
        self.strategy = strategy
        self.bought = {}  # type: Dict[Offer, Market]
        self.posted = {}  # type: Dict[Offer, Market]
        self.sold = defaultdict(list)  # type: Dict[Market, List[str]]
        self.changed = {}  # type: Dict[str, Offer]

    @property
    def open(self):
        return {offer: market
                for offer, market in self.posted.items()
                if offer.id not in self.sold[market]}

    def bought_offer(self, offer, market):
        self.bought[offer] = market

    def sold_offer(self, offer_id, market):
        self.sold[market].append(offer_id)

    def _update_offer(self, offer):
        old_offer_list = [o for o in self.posted.keys() if o.id == offer.id]
        assert len(old_offer_list) == 1, "Expected to find a unique offer to update"
        old_offer = old_offer_list[0]
        self.posted[offer] = self.posted.pop(old_offer)

    def bought_in_market(self, market):
        return [offer for offer, _market in self.bought.items() if market == _market]

    def open_in_market(self, market):
        return [offer
                for offer, _market in self.posted.items()
                if market == _market and offer.id not in self.sold[market]]

    def posted_in_market(self, market):
        return [offer for offer, _market in self.posted.items() if market == _market]

    def sold_in_market(self, market):
        return [offer
                for offer in self.posted_in_market(market)
                if offer.id in self.sold[market]]

    def post(self, offer, market):
        self.posted[offer] = market

    def remove(self, offer):
        try:
            market = self.posted.pop(offer)
            if offer.id in self.sold[market]:
                self.strategy.log.error("Offer already sold, cannot remove it.")
                self.posted[offer] = market
            else:
                return True
        except KeyError:
            self.strategy.log.warn("Could not find offer to remove")

    def replace(self, old_offer, new_offer, market):
        if self.remove(old_offer):
            self.post(new_offer, market)

    def on_trade(self, market, trade):
        try:
            if trade.offer.seller == self.strategy.owner.name:
                if trade.offer.id in self.changed:
                    self._update_offer(trade.offer)
                    self.post(self.changed.pop(trade.offer.id), market)
                self.sold_offer(trade.offer.id, market)
        except AttributeError:
            raise SimulationException("Trade event before strategy was initialized.")

    def on_offer_changed(self, market, existing_offer, new_offer):
        if existing_offer.seller == self.strategy.owner.name:
            assert existing_offer.id not in self.changed, \
                   "Offer should only change once before each trade."
            self.changed[existing_offer.id] = new_offer


class BaseStrategy(TriggerMixin, EventMixin, AreaBehaviorBase):
    available_triggers = [
        Trigger('enable', state_getter=lambda s: s.enabled, help="Enable trading"),
        Trigger('disable', state_getter=lambda s: not s.enabled, help="Disable trading")
    ]

    def __init__(self):
        super(BaseStrategy, self).__init__()
        self.offers = Offers(self)
        self.enabled = True

    parameters = None

    def non_attr_parameters(self):
        return dict()

    @property
    def trades(self):
        return _TradeLookerUpper(self.owner.name)

    def energy_balance(self, market, *, allow_open_market=False):
        """
        Return own energy balance for a particular market.

        Negative values indicate bought energy, postive ones sold energy.
        """
        if not allow_open_market and not market.readonly:
            raise ValueError(
                'Energy balance for open market requested and `allow_open_market` no passed')
        return sum(
            t.offer.energy * -1
            if t.buyer == self.owner.name
            else t.offer.energy
            for t in self.trades[market]
        )

    def accept_offer(self, market: Market, offer, *, buyer=None, energy=None):
        if buyer is None:
            buyer = self.owner.name
        if not isinstance(offer, Offer):
            offer = market.offers[offer]
        trade = market.accept_offer(offer, buyer, energy=energy)
        self.offers.bought_offer(trade.offer, market)
        return trade

    def post(self, **data):
        self.event_data_received(data)

    def event_data_received(self, data: Dict[str, Any]):
        pass

    def trigger_enable(self, **kw):
        self.enabled = True
        self.log.warning("Trading has been enabled")

    def trigger_disable(self):
        self.enabled = False
        self.log.warning("Trading has been disabled")
        # We've been disabled - remove all future open offers
        for market in self.area.markets.values():
            for offer in list(market.offers.values()):
                if offer.seller == self.owner.name:
                    market.delete_offer(offer)

    def event_listener(self, event_type: Union[AreaEvent, MarketEvent], **kwargs):
        if self.enabled or event_type in (AreaEvent.ACTIVATE, MarketEvent.TRADE):
            super().event_listener(event_type, **kwargs)

    def event_trade(self, *, market, trade):
        self.offers.on_trade(market, trade)

    def event_offer_changed(self, *, market, existing_offer, new_offer):
        self.offers.on_offer_changed(market, existing_offer, new_offer)
