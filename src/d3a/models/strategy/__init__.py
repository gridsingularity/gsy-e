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
from logging import getLogger
from typing import List, Dict, Any, Union  # noqa

from d3a.d3a_core.exceptions import SimulationException
from d3a.models.base import AreaBehaviorBase
from d3a.models.market import Market
from d3a.models.market.market_structures import Offer
from d3a_interface.constants_limits import ConstSettings

from d3a.d3a_core.device_registry import DeviceRegistry
from d3a.events.event_structures import Trigger, TriggerMixin, AreaEvent, MarketEvent
from d3a.events import EventMixin
from d3a.d3a_core.util import append_or_create_key

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
        self.bought = {}  # type: Dict[Offer, Str]
        self.posted = {}  # type: Dict[Offer, Str]
        self.sold = {}  # type: Dict[Str, List[str]]
        self.changed = {}  # type: Dict[str, Offer]

    @property
    def area(self):
        # TODO: Remove the owner and area distinction from the AreaBehaviorBase class
        return self.strategy.area if self.strategy.area is not None else self.strategy.owner

    def _delete_past_offers(self, existing_offers):
        offers = {}
        for offer, market_id in existing_offers.items():
            market = self.area.get_future_market_from_id(market_id)
            if market is not None:
                offers[offer] = market_id
        return offers

    def delete_past_markets_offers(self):
        self.posted = self._delete_past_offers(self.posted)
        self.bought = self._delete_past_offers(self.bought)
        self.changed = {}

    @property
    def open(self):
        open_offers = {}
        for offer, market_id in self.posted.items():
            if market_id not in self.sold:
                self.sold[market_id] = []
            if offer.id not in self.sold[market_id]:
                open_offers[offer] = market_id
        return open_offers

    def bought_offer(self, offer, market_id):
        self.bought[offer] = market_id

    def sold_offer(self, offer_id, market_id):
        self.sold = append_or_create_key(self.sold, market_id, offer_id)

    def _update_offer(self, offer):
        old_offer_list = [o for o in self.posted.keys() if o.id == offer.id]
        assert len(old_offer_list) <= 1, "Expected to find a unique offer to update"
        if len(old_offer_list) == 0:
            return
        old_offer = old_offer_list[0]
        self.posted[offer] = self.posted.pop(old_offer)

    def posted_in_market(self, market_id):
        return [offer for offer, _market in self.posted.items() if market_id == _market]

    def sold_in_market(self, market_id):
        sold_offers = []
        for offer in self.posted_in_market(market_id):
            if market_id not in self.sold:
                self.sold[market_id] = []
            if offer.id in self.sold[market_id]:
                sold_offers.append(offer)
        return sold_offers

    def post(self, offer, market_id):
        self.posted[offer] = market_id

    def remove(self, offer):
        try:
            market_id = self.posted.pop(offer)
            assert type(market_id) == str
            if market_id in self.sold and offer.id in self.sold[market_id]:
                self.strategy.log.warning("Offer already sold, cannot remove it.")
                self.posted[offer] = market_id
            else:
                return True
        except KeyError:
            self.strategy.log.warning("Could not find offer to remove")

    def replace(self, old_offer, new_offer, market):
        if self.remove(old_offer):
            self.post(new_offer, market.id)

    def on_trade(self, market_id, trade):
        try:
            if trade.offer.seller == self.strategy.owner.name:
                if trade.offer.id in self.changed:
                    self._update_offer(trade.offer)
                    self.post(self.changed.pop(trade.offer.id), market_id)
                self.sold_offer(trade.offer.id, market_id)
        except AttributeError:
            raise SimulationException("Trade event before strategy was initialized.")

    def on_offer_changed(self, existing_offer, new_offer):
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

    def area_reconfigure_event(self, *args, **kwargs):
        pass

    def event_on_disabled_area(self):
        pass

    def read_config_event(self):
        pass

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

    @property
    def is_eligible_for_balancing_market(self):
        if self.owner.name in DeviceRegistry.REGISTRY and \
                ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
            return True

    def accept_offer(self, market: Market, offer, *, buyer=None, energy=None,
                     already_tracked=False, trade_rate: float = None,
                     original_trade_rate: float = None):
        if buyer is None:
            buyer = self.owner.name
        if not isinstance(offer, Offer):
            offer = market.offers[offer]
        trade = market.accept_offer(offer, buyer, energy=energy, trade_rate=trade_rate,
                                    already_tracked=already_tracked,
                                    original_trade_rate=original_trade_rate)
        self.offers.bought_offer(trade.offer, market.id)
        return trade

    def post(self, **data):
        self.event_data_received(data)

    def event_data_received(self, data: Dict[str, Any]):
        pass

    def trigger_enable(self, **kw):
        self.enabled = True
        self.log.info("Trading has been enabled")

    def trigger_disable(self):
        self.enabled = False
        self.log.info("Trading has been disabled")
        # We've been disabled - remove all future open offers
        for market in self.area.markets.values():
            for offer in list(market.offers.values()):
                if offer.seller == self.owner.name:
                    market.delete_offer(offer)

    def event_listener(self, event_type: Union[AreaEvent, MarketEvent], **kwargs):
        if self.enabled or event_type in (AreaEvent.ACTIVATE, MarketEvent.TRADE):
            super().event_listener(event_type, **kwargs)

    def event_trade(self, *, market_id, trade):
        self.offers.on_trade(market_id, trade)

    def event_offer_changed(self, *, market_id, existing_offer, new_offer):
        self.offers.on_offer_changed(existing_offer, new_offer)

    def event_market_cycle(self):
        if not ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            self.offers.delete_past_markets_offers()


class BidEnabledStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self._bids = {}
        self._traded_bids = {}

    def post_bid(self, market, price, energy):
        bid = market.bid(
            price,
            energy,
            self.owner.name,
            self.area.name,
            original_bid_price=price
        )
        self.add_bid_to_posted(market.id, bid)
        return bid

    def remove_bid_from_pending(self, bid_id, market_id):
        market = self.area.get_future_market_from_id(market_id)
        if market is None:
            return
        if bid_id in market.bids.keys():
            market.delete_bid(bid_id)
        self._bids[market.id] = [bid for bid in self._bids[market.id] if bid.id != bid_id]

    def add_bid_to_posted(self, market_id, bid):
        if market_id not in self._bids.keys():
            self._bids[market_id] = []
        self._bids[market_id].append(bid)

    def add_bid_to_bought(self, bid, market_id, remove_bid=True):
        if market_id not in self._traded_bids:
            self._traded_bids[market_id] = []
        self._traded_bids[market_id].append(bid)
        if remove_bid:
            self.remove_bid_from_pending(bid.id, market_id)

    def get_traded_bids_from_market(self, market):
        if market.id not in self._traded_bids:
            return []
        else:
            return self._traded_bids[market.id]

    def are_bids_posted(self, market_id):
        if market_id not in self._bids:
            return False
        return len(self._bids[market_id]) > 0

    def get_posted_bids(self, market):
        if market.id not in self._bids:
            return {}
        return self._bids[market.id]

    def event_bid_deleted(self, *, market_id, bid):
        assert ConstSettings.IAASettings.MARKET_TYPE is not 1, \
            "Invalid state, cannot receive a bid if single sided market is globally configured."

        if bid.buyer != self.owner.name:
            return
        self.remove_bid_from_pending(bid.id, market_id)

    def event_bid_changed(self, *, market_id, existing_bid, new_bid):
        assert ConstSettings.IAASettings.MARKET_TYPE is not 1, \
            "Invalid state, cannot receive a bid if single sided market is globally configured."
        if new_bid.buyer != self.owner.name:
            return
        self.add_bid_to_posted(market_id, bid=new_bid)

    def event_bid_traded(self, *, market_id, bid_trade):
        assert ConstSettings.IAASettings.MARKET_TYPE is not 1, \
            "Invalid state, cannot receive a bid if single sided market is globally configured."

        if bid_trade.buyer == self.owner.name:
            self.add_bid_to_bought(bid_trade.offer, market_id)

    def event_market_cycle(self):
        if not ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            self._bids = {}
            self._traded_bids = {}
            super().event_market_cycle()
