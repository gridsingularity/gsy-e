import random
import uuid
from collections import defaultdict, namedtuple
from itertools import groupby
from logging import getLogger
from operator import itemgetter
from threading import Lock
from typing import Any, Dict, List, Set, Union  # noqa

import sys

from ethereum.utils import encode_hex, decode_hex
from pendulum.pendulum import Pendulum
from terminaltables.other_tables import SingleTable

from d3a.exceptions import InvalidOffer, MarketReadOnlyException, OfferNotFoundException, \
    InvalidTrade
from d3a.models.events import MarketEvent, OfferEvent


BC_EVENT_MAP = {
    b"NewOffer": MarketEvent.OFFER,
    b"CancelOffer": MarketEvent.OFFER_DELETED,
    b"Trade": MarketEvent.TRADE,
    b"OfferChanged": MarketEvent.OFFER_CHANGED
}
BC_NUM_FACTOR = 10 ** 10

log = getLogger(__name__)


class Offer:
    def __init__(self, id, price, energy, seller, market=None):
        self.id = str(id)
        self.price = price
        self.energy = energy
        self.seller = seller
        self.market = market
        self._listeners = defaultdict(set)  # type: Dict[OfferEvent, Set[callable]]

    def __repr__(self):
        return "<Offer('{s.id!s:.6s}', '{s.energy} kWh@{s.price}', '{s.seller}'>".format(s=self)

    def __str__(self):
        return "{{{s.id!s:.6s}}} [{s.seller}]: {s.energy} kWh @ {s.price}".format(s=self)

    def add_listener(self, event: Union[OfferEvent, List[OfferEvent]], listener):
        if isinstance(event, (tuple, list)):
            for ev in event:
                self.add_listener(ev, listener)
        else:
            self._listeners[event].add(listener)

    def _call_listeners(self, event: OfferEvent, **kwargs):
        # Call listeners in random order to ensure fairness
        for listener in sorted(self._listeners[event], key=lambda l: random.random()):
            listener(**kwargs, offer=self)

    # XXX: This might be unreliable - decide after testing
    def __del__(self):
        self._call_listeners(OfferEvent.DELETED)

    def _traded(self, trade: 'Trade', market: 'Market'):
        """
        Called by `Market` to inform listeners about the trade
        """
        self._call_listeners(OfferEvent.ACCEPTED, market=market, trade=trade)


class Trade(namedtuple('Trade', ('id', 'time', 'offer', 'seller', 'buyer'))):
    def __str__(self):
        return (
            "{{{s.id!s:.6s}}} [{s.seller} -> {s.buyer}] "
            "{s.offer.energy} kWh @ {s.offer.price}".format(s=self)
        )


class Market:
    def __init__(self, time_slot=None, area=None, notification_listener=None, readonly=False):
        from d3a.models.area import Area
        self.area = area  # type: Area
        assert isinstance(self.area, Area)
        self.time_slot = time_slot
        self.readonly = readonly
        # offer-id -> Offer
        self.offers = {}  # type: Dict[str, Offer]
        self.offers_deleted = {}  # type: Dict[str, Offer]
        self.notification_listeners = []
        self.trades = []  # type: List[Trade]
        # Store trades temporarily until bc event has fired
        self._trades_by_id = {}  # type: Dict[str, Trade]
        self.ious = defaultdict(lambda: defaultdict(int))
        self.traded_energy = defaultdict(int)
        # Store actual energy consumption in a nested dict in the form of
        # Timestamp -> Actor -> Value
        self.actual_energy = defaultdict(
            lambda: defaultdict(int))  # type: Dict[Pendulum, Dict[str, float]]
        self.min_trade_price = sys.maxsize
        self._avg_trade_price = None
        self.max_trade_price = 0
        self.min_offer_price = sys.maxsize
        self._avg_offer_price = None
        self.max_offer_price = 0
        self.offer_lock = Lock()
        self.trade_lock = Lock()
        if notification_listener:
            self.notification_listeners.append(notification_listener)
        self.bc_contract = None
        if self.area.bc:
            self.bc_contract = self.area.bc.init_contract(
                "Market",
                [
                    self.area.bc.contracts['ClearingToken'].address,
                    self.area.config.duration.in_seconds()
                ],
                [self._bc_listener]
            )

    def add_listener(self, listener):
        self.notification_listeners.append(listener)

    def _bc_listener(self, event):
        event_type = BC_EVENT_MAP[event['_event_type']]
        kwargs = {}
        if event_type is MarketEvent.OFFER:
            kwargs['offer'] = self.offers[encode_hex(event['offerId'])]
        elif event_type is MarketEvent.OFFER_DELETED:
            kwargs['offer'] = self.offers_deleted.pop(encode_hex(event['offerId']))
        elif event_type is MarketEvent.OFFER_CHANGED:
            raise NotImplementedError("Partial trades not yet supported when using blockchain")
        elif event_type is MarketEvent.TRADE:
            kwargs['trade'] = self._trades_by_id.pop(encode_hex(event['tradeId']))
        self._notify_listeners(event_type, **kwargs)

    def _notify_listeners(self, event, **kwargs):
        # Deliver notifications in random order to ensure fairness
        for listener in sorted(self.notification_listeners, key=lambda l: random.random()):
            listener(event, market=self, **kwargs)

    def offer(self, price: float, energy: float, seller: str) -> Offer:
        if self.readonly:
            raise MarketReadOnlyException()
        if energy <= 0:
            raise InvalidOffer()
        if self.bc_contract:
            offer_id = encode_hex(
                self.bc_contract.offer(
                    int(energy * BC_NUM_FACTOR),
                    int(price * BC_NUM_FACTOR),
                    sender=self.area.bc.users[seller].privkey
                )
            )
        else:
            offer_id = str(uuid.uuid4())
        offer = Offer(offer_id, price, energy, seller, self)
        with self.offer_lock:
            self.offers[offer.id] = offer
            log.info("[OFFER][NEW] %s", offer)
            self._update_min_max_avg_offer_prices()
        if self.area.bc:
            self.area.bc.fire_delayed_listeners()
        else:
            self._notify_listeners(MarketEvent.OFFER, offer=offer)
        return offer

    def delete_offer(self, offer_or_id: Union[str, Offer]):
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        with self.offer_lock:
            if self.bc_contract:
                self.bc_contract.cancel(offer_or_id)
            offer = self.offers.pop(offer_or_id, None)
            self._update_min_max_avg_offer_prices()
            if not offer:
                raise OfferNotFoundException()
            log.info("[OFFER][DEL] %s", offer)
            if self.bc_contract:
                # Hold on to deleted offer until bc event is processed
                self.offers_deleted[offer_or_id] = offer
        if self.area.bc:
            self.area.bc.fire_delayed_listeners()
        else:
            self._notify_listeners(MarketEvent.OFFER_DELETED, offer=offer)

    def accept_offer(self, offer_or_id: Union[str, Offer], buyer: str, *, energy: int = None,
                     time: Pendulum = None) -> Trade:
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        with self.offer_lock, self.trade_lock:
            offer = self.offers.pop(offer_or_id, None)
            if offer is None:
                raise OfferNotFoundException()
            try:
                if time is None:
                    time = self._now
                if energy is not None:
                    # Partial trade
                    if energy == 0:
                        raise InvalidTrade("Energy can not be zero.")
                    elif energy < offer.energy:
                        original_offer = offer
                        accepted_offer = Offer(
                            offer.id,
                            offer.price / offer.energy * energy,
                            energy,
                            offer.seller,
                            offer.market
                        )
                        residual_offer = Offer(
                            str(uuid.uuid4()),
                            offer.price / offer.energy * (offer.energy - energy),
                            offer.energy - energy,
                            offer.seller,
                            offer.market
                        )
                        self.offers[residual_offer.id] = residual_offer
                        log.info("[OFFER][CHANGED] %s -> %s", original_offer, residual_offer)
                        offer = accepted_offer
                        if not self.area.bc:
                            self._notify_listeners(
                                MarketEvent.OFFER_CHANGED,
                                existing_offer=original_offer,
                                new_offer=residual_offer
                            )
                    elif energy > offer.energy:
                        raise InvalidTrade("Energy can't be greater than offered energy")
                    else:
                        # Requested partial is equal to offered energy - just proceed normally
                        pass
            except:  # noqa
                # Exception happened - restore offer
                self.offers[offer.id] = offer
                raise

            if self.bc_contract:
                success, _, trade_id = self.bc_contract.trade(
                    decode_hex(offer.id),
                    int(offer.energy * BC_NUM_FACTOR),
                    sender=self.area.bc.users[buyer].privkey
                )
                trade_id = encode_hex(trade_id)
            else:
                trade_id = uuid.uuid4()
            trade = Trade(trade_id, time, offer, offer.seller, buyer)
            self.trades.append(trade)
            if self.bc_contract:
                self._trades_by_id[trade_id] = trade
            log.warning("[TRADE] %s", trade)
            # FIXME: The following updates need to be done in response to the BC event
            self.traded_energy[offer.seller] += offer.energy
            self.traded_energy[buyer] -= offer.energy
            self.ious[buyer][offer.seller] += offer.price
            self._update_min_max_avg_trade_prices(offer.price / offer.energy)
            # Recalculate offer min/max price since offer was removed
            self._update_min_max_avg_offer_prices()
        # FIXME: Needs to be triggered by blockchain event
        offer._traded(trade, self)
        if self.area.bc:
            self.area.bc.fire_delayed_listeners()
        else:
            self._notify_listeners(MarketEvent.TRADE, trade=trade)
        return trade

    def _update_min_max_avg_offer_prices(self):
        self._avg_offer_price = None
        offer_prices = [o.price / o.energy for o in self.offers.values()]
        if offer_prices:
            self.min_offer_price = round(min(offer_prices), 4)
            self.min_offer_price = round(max(offer_prices), 4)

    def _update_min_max_avg_trade_prices(self, price):
        self.max_trade_price = round(max(self.max_trade_price, price), 4)
        self.min_trade_price = round(min(self.min_trade_price, price), 4)
        self._avg_trade_price = None
        self._avg_offer_price = None

    def __repr__(self):  # pragma: no cover
        return "<Market{} offers: {} (E: {} kWh V: {}) trades: {} (E: {} kWh, V: {})>".format(
            " {:%H:%M}".format(self.time_slot) if self.time_slot else "",
            len(self.offers),
            sum(o.energy for o in self.offers.values()),
            sum(o.price for o in self.offers.values()),
            len(self.trades),
            sum(t.offer.energy for t in self.trades),
            sum(t.offer.price for t in self.trades)
        )

    @property
    def avg_offer_price(self):
        if self._avg_offer_price is None:
            with self.offer_lock:
                price = sum(o.price for o in self.offers.values())
                energy = sum(o.energy for o in self.offers.values())
            self._avg_offer_price = round(price / energy, 4) if energy else 0
        return self._avg_offer_price

    @property
    def avg_trade_price(self):
        if self._avg_trade_price is None:
            with self.trade_lock:
                price = sum(t.offer.price for t in self.trades)
                energy = sum(t.offer.energy for t in self.trades)
            self._avg_trade_price = round(price / energy, 4) if energy else 0
        return self._avg_trade_price

    @property
    def sorted_offers(self):
        return sorted(self.offers.values(), key=lambda o: o.price / o.energy)

    @property
    def _now(self):
        if self.area:
            return self.area.now
        log.error("No area available. Using real system time!")
        return Pendulum.now()

    @property
    def actual_energy_agg(self):
        return {
            actor: sum(value for _, value in items)
            for actor, items
            in groupby(
                sorted(
                    (
                        (actor, value)
                        for report_dicts in list(self.actual_energy.values())
                        for actor, value in list(report_dicts.items())
                    ),
                    key=itemgetter(0)
                ),
                key=itemgetter(0)
            )
        }

    def display(self):  # pragma: no cover
        out = []
        if self.offers:
            out.append("Offers:")
            offer_table = [['From', 'kWh', 'Value']] + [
                [o.seller, o.energy, o.price]
                for o in self.offers.values()
            ]
            try:
                out.append(SingleTable(offer_table).table)
            except:  # noqa
                # Could blow up with certain unicode characters
                pass
        if self.trades:
            out.append("Trades:")
            trade_table = [['From', 'To', 'kWh', 'Value']] + [
                [trade.seller, trade.buyer, trade.offer.energy, trade.offer.price]
                for trade in self.trades
            ]
            try:
                out.append(SingleTable(trade_table).table)
            except:  # noqa
                # Could blow up with certain unicode characters
                pass
        if self.traded_energy:
            out.append("Traded Energy:")
            acct_table = [['Actor', 'Sum (kWh)']] + [
                [actor, energy]
                for actor, energy in self.traded_energy.items()
            ]
            try:
                out.append(SingleTable(acct_table).table)
            except:  # noqa
                # Could blow up with certain unicode characters
                pass
        return "\n".join(out)

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['offer_lock']
        del state['trade_lock']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.offer_lock = Lock()
        self.trade_lock = Lock()
