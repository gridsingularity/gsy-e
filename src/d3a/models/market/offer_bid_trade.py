import random

from collections import defaultdict, namedtuple
from typing import Dict, List, Set, Union  # noqa
from d3a.models.events import OfferEvent


class Offer:
    def __init__(self, id, price, energy, seller, market=None):
        self.id = str(id)
        self.real_id = id
        self.price = price
        self.energy = energy
        self.seller = seller
        self.market = market
        self._listeners = defaultdict(set)  # type: Dict[OfferEvent, Set[callable]]

    def __repr__(self):
        return "<Offer('{s.id!s:.6s}', '{s.energy} kWh@{s.price}', '{s.seller} {rate}'>"\
            .format(s=self, rate=self.price / self.energy)

    def __str__(self):
        return "{{{s.id!s:.6s}}} [{s.seller}]: {s.energy} kWh @ {s.price} @ {rate}"\
            .format(s=self, rate=self.price / self.energy)

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


class Bid(namedtuple('Bid', ('id', 'price', 'energy', 'buyer', 'seller', 'market'))):
    def __new__(cls, id, price, energy, buyer, seller, market=None):
        # overridden to give the residual field a default value
        return super(Bid, cls).__new__(cls, str(id), price, energy, buyer, seller, market)

    def __repr__(self):
        return (
            "<Bid {{{s.id!s:.6s}}} [{s.buyer}] [{s.seller}] "
            "{s.energy} kWh @ {s.price} {rate}>".format(s=self, rate=self.price / self.energy)
        )

    def __str__(self):
        return (
            "{{{s.id!s:.6s}}} [{s.buyer}] [{s.seller}] "
            "{s.energy} kWh @ {s.price} {rate}".format(s=self, rate=self.price / self.energy)
        )


class Trade(namedtuple('Trade', ('id', 'time', 'offer', 'seller',
                                 'buyer', 'residual', 'price_drop',
                                 'already_tracked'))):
    def __new__(cls, id, time, offer, seller, buyer, residual=None,
                price_drop=False, already_tracked=False):
        # overridden to give the residual field a default value
        return super(Trade, cls).__new__(cls, id, time, offer, seller, buyer, residual,
                                         price_drop, already_tracked)

    def __str__(self):
        mark_partial = "(partial)" if self.residual is not None else ""
        return (
            "{{{s.id!s:.6s}}} [{s.seller} -> {s.buyer}] "
            "{s.offer.energy} kWh {p} @ {s.offer.price} {rate} {s.offer.id}".
            format(s=self, p=mark_partial, rate=self.offer.price / self.offer.energy)
        )

    @classmethod
    def _csv_fields(cls):
        return (cls._fields[:2] + ('rate [ct./kWh]', 'energy [kWh]') +
                cls._fields[3:5])

    def _to_csv(self):
        rate = round(self.offer.price / self.offer.energy, 4)
        return self[:2] + (rate, self.offer.energy) + self[3:5]


class BalancingOffer(Offer):

    def __repr__(self):
        return "<BalancingOffer('{s.id!s:.6s}', '{s.energy} kWh@{s.price}', '{s.seller} {rate}'>"\
            .format(s=self, rate=self.price / self.energy)

    def __str__(self):
        return "<BalancingOffer{{{s.id!s:.6s}}} [{s.seller}]: " \
               "{s.energy} kWh @ {s.price} @ {rate}>".format(s=self,
                                                             rate=self.price / self.energy)


class BalancingTrade(namedtuple('BalancingTrade', ('id', 'time', 'offer', 'seller',
                                                   'buyer', 'residual', 'price_drop'))):
    def __new__(cls, id, time, offer, seller, buyer, residual=None, price_drop=False):
        # overridden to give the residual field a default value
        return super(BalancingTrade, cls).__new__(cls, id, time, offer, seller,
                                                  buyer, residual, price_drop)

    def __str__(self):
        mark_partial = "(partial)" if self.residual is not None else ""
        return (
            "{{{s.id!s:.6s}}} [{s.seller} -> {s.buyer}] "
            "{s.offer.energy} kWh {p} @ {s.offer.price} {rate} {s.offer.id}".
            format(s=self, p=mark_partial, rate=self.offer.price / self.offer.energy)
        )

    @classmethod
    def _csv_fields(cls):
        return (cls._fields[:2] + ('rate [ct./kWh]', 'energy [kWh]') +
                cls._fields[3:5])

    def _to_csv(self):
        rate = round(self.offer.price / self.offer.energy, 4)
        return self[:2] + (rate, self.offer.energy) + self[3:5]
