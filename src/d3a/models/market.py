import random
import uuid
from collections import defaultdict, namedtuple
from logging import getLogger
from typing import Dict, List, Set, Union  # noqa

import sys

from pendulum import DateTime
from terminaltables.other_tables import SingleTable

from d3a import TIME_ZONE
from d3a import TIME_FORMAT
from d3a.exceptions import InvalidOffer, MarketReadOnlyException, OfferNotFoundException, \
    InvalidTrade, InvalidBid, BidNotFound, InvalidBalancingTradeException, DeviceNotInRegistryError
from d3a.models.events import MarketEvent, OfferEvent
from d3a.device_registry import DeviceRegistry
from d3a.blockchain_utils import create_market_contract, create_new_offer, cancel_offer, \
    trade_offer

BC_EVENT_MAP = {
    b"NewOffer": MarketEvent.OFFER,
    b"CancelOffer": MarketEvent.OFFER_DELETED,
    b"NewTrade": MarketEvent.TRADE,
    b"OfferChanged": MarketEvent.OFFER_CHANGED
}

log = getLogger(__name__)


OFFER_PRICE_THRESHOLD = 0.00001


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


class Market:
    def __init__(self, time_slot=None, area=None, notification_listener=None, readonly=False):
        self.area = area
        self.time_slot = time_slot
        self.time_slot_str = time_slot.strftime(TIME_FORMAT) \
            if self.time_slot is not None \
            else None
        self.readonly = readonly
        # offer-id -> Offer
        self.offers = {}  # type: Dict[str, Offer]
        self.offers_deleted = {}  # type: Dict[str, Offer]
        self.offers_changed = {}  # type: Dict[str, (Offer, Offer)]
        self.bids = {}  # type: Dict[str, Bid]
        self.notification_listeners = []
        self.trades = []  # type: List[Trade]
        # Store trades temporarily until bc event has fired
        self._trades_by_id = {}  # type: Dict[str, Trade]
        self.ious = defaultdict(lambda: defaultdict(int))
        self.traded_energy = defaultdict(int)
        # Store actual energy consumption in a nested dict in the form of
        # Timestamp -> Actor -> Value
        self.actual_energy = defaultdict(
            lambda: defaultdict(int))  # type: Dict[DateTime, Dict[str, float]]
        self.accumulated_actual_energy_agg = {}
        self.min_trade_price = sys.maxsize
        self._avg_trade_price = None
        self.max_trade_price = 0
        self.min_offer_price = sys.maxsize
        self._avg_offer_price = None
        self.max_offer_price = 0
        self._sorted_offers = []
        self.accumulated_trade_price = 0
        self.accumulated_trade_energy = 0
        if notification_listener:
            self.notification_listeners.append(notification_listener)
        self.bc_contract = \
            create_market_contract(self.area.bc,
                                   self.area.config.duration.in_seconds(),
                                   [self._bc_listener]) \
            if self.area and self.area.bc \
            else None
        self.device_registry = DeviceRegistry.REGISTRY

    def add_listener(self, listener):
        self.notification_listeners.append(listener)

    def _bc_listener(self, event):
        # TODO: Disabled for now, should be added once event driven blockchain transaction
        # handling is introduced
        # event_type = BC_EVENT_MAP[event['_event_type']]
        # kwargs = {}
        # if event_type is MarketEvent.OFFER:
        #     kwargs['offer'] = self.offers[event['offerId']]
        # elif event_type is MarketEvent.OFFER_DELETED:
        #     kwargs['offer'] = self.offers_deleted.pop(event['offerId'])
        # elif event_type is MarketEvent.OFFER_CHANGED:
        #     existing_offer, new_offer = self.offers_changed.pop(event['oldOfferId'])
        #     kwargs['existing_offer'] = existing_offer
        #     kwargs['new_offer'] = new_offer
        # elif event_type is MarketEvent.TRADE:
        #     kwargs['trade'] = self._trades_by_id.pop(event['tradeId'])
        # self._notify_listeners(event_type, **kwargs)
        return

    def _notify_listeners(self, event, **kwargs):
        # Deliver notifications in random order to ensure fairness
        for listener in sorted(self.notification_listeners, key=lambda l: random.random()):
            listener(event, market=self, **kwargs)

    def offer(self, price: float, energy: float, seller: str,
              balancing_agent: bool=False) -> Offer:
        assert balancing_agent is False
        if self.readonly:
            raise MarketReadOnlyException()
        if energy <= 0:
            raise InvalidOffer()

        offer_id = create_new_offer(self.area.bc, self.bc_contract, energy, price, seller) \
            if self.bc_contract \
            else str(uuid.uuid4())

        offer = Offer(offer_id, price, energy, seller, self)
        self.offers[offer.id] = offer
        self._sorted_offers = sorted(self.offers.values(), key=lambda o: o.price / o.energy)
        log.info(f"[OFFER][NEW][{self.time_slot_str}] {offer}")
        self._update_min_max_avg_offer_prices()
        self._notify_listeners(MarketEvent.OFFER, offer=offer)
        return offer

    def bid(self, price: float, energy: float, buyer: str, seller: str, bid_id: str=None) -> Bid:
        if energy <= 0:
            raise InvalidBid()
        bid = Bid(str(uuid.uuid4()) if bid_id is None else bid_id,
                  price, energy, buyer, seller, self)
        self.bids[bid.id] = bid
        log.info(f"[BID][NEW][{self.time_slot_str}] {bid}")
        return bid

    def delete_offer(self, offer_or_id: Union[str, Offer]):
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id

        offer = self.offers.pop(offer_or_id, None)

        if self.bc_contract and offer is not None:
            cancel_offer(self.area.bc, self.bc_contract, offer.real_id, offer.seller)
            # Hold on to deleted offer until bc event is processed
            self.offers_deleted[offer_or_id] = offer
        self._sorted_offers = sorted(self.offers.values(), key=lambda o: o.price / o.energy)
        self._update_min_max_avg_offer_prices()
        if not offer:
            raise OfferNotFoundException()
        log.info(f"[OFFER][DEL][{self.time_slot_str}] {offer}")

        # TODO: Once we add event-driven blockchain, this should be asynchronous
        self._notify_listeners(MarketEvent.OFFER_DELETED, offer=offer)

    def delete_bid(self, bid_or_id: Union[str, Bid]):
        if isinstance(bid_or_id, Bid):
            bid_or_id = bid_or_id.id
        bid = self.bids.pop(bid_or_id, None)
        if not bid:
            raise BidNotFound(bid_or_id)
        log.info(f"[BID][DEL][{self.time_slot_str}] {bid}")
        self._notify_listeners(MarketEvent.BID_DELETED, bid=bid)

    def accept_bid(self, bid: Bid, energy: float = None,
                   seller: str = None, buyer: str = None, already_tracked: bool = False,
                   price_drop: bool = True):
        market_bid = self.bids.pop(bid.id, None)
        if market_bid is None:
            raise BidNotFound("During accept bid: " + str(bid))

        seller = market_bid.seller if seller is None else seller
        buyer = market_bid.buyer if buyer is None else buyer
        energy = market_bid.energy if energy is None else energy
        if energy <= 0:
            raise InvalidTrade("Energy cannot be zero.")
        elif energy > bid.energy:
            raise InvalidTrade("Traded energy cannot be more than the bid energy.")
        elif energy is None or energy <= market_bid.energy:
            residual = False
            if energy < market_bid.energy:
                # Partial bidding
                residual = True
                energy_rate = market_bid.price / market_bid.energy
                final_price = energy * energy_rate
                residual_energy = market_bid.energy - energy
                residual_price = residual_energy * energy_rate
                self.bid(residual_price, residual_energy, buyer, seller, bid.id)
                bid = Bid(bid.id, final_price, energy,
                          buyer, seller, self)

            trade = Trade(str(uuid.uuid4()), self._now,
                          bid, seller, buyer, residual, price_drop=price_drop,
                          already_tracked=already_tracked)
            self._update_stats_after_trade(trade, bid, bid.buyer, already_tracked)
            if not already_tracked:
                log.warning(f"[TRADE][BID][{self.time_slot_str}] {trade}")

            self._notify_listeners(MarketEvent.BID_TRADED, bid_trade=trade)
            if not trade.residual:
                self._notify_listeners(MarketEvent.BID_DELETED, bid=market_bid)
            return trade
        else:
            raise Exception("Undefined state or conditions. Should never reach this place.")

    def accept_offer(self, offer_or_id: Union[str, Offer], buyer: str, *, energy: int = None,
                     time: DateTime = None, price_drop: bool = False) -> Trade:
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        offer = self.offers.pop(offer_or_id, None)
        original_offer = offer
        residual_offer = None
        self._sorted_offers = sorted(self.offers.values(),
                                     key=lambda o: o.price / o.energy)
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
                    accepted_offer_id = offer.id \
                        if self.area is None or self.area.bc is None \
                        else offer.real_id
                    accepted_offer = Offer(
                        accepted_offer_id,
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
                    log.info(f"[OFFER][CHANGED][{self.time_slot_str}] "
                             f"{original_offer} -> {residual_offer}")
                    offer = accepted_offer
                    if self.area and self.area.bc:
                        self.offers_changed[offer.id] = (original_offer, residual_offer)
                    else:
                        self._sorted_offers = sorted(self.offers.values(),
                                                     key=lambda o: o.price / o.energy)
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
        except Exception:
            # Exception happened - restore offer
            self.offers[offer.id] = offer
            self._sorted_offers = sorted(self.offers.values(),
                                         key=lambda o: o.price / o.energy)
            raise

        trade_id = self._handle_blockchain_trade_event(offer, buyer,
                                                       original_offer, residual_offer)
        trade = Trade(trade_id, time, offer, offer.seller, buyer, residual_offer, price_drop)
        if self.area and self.area.bc:
            self._trades_by_id[trade_id] = trade

        self._update_stats_after_trade(trade, offer, buyer)
        log.warning(f"[TRADE][{self.time_slot_str}] {trade}")

        # FIXME: Needs to be triggered by blockchain event
        # TODO: Same as above, should be modified when event-driven blockchain is introduced
        offer._traded(trade, self)

        # TODO: Use non-blockchain non-event-driven version for now for both blockchain and
        # normal runs.
        self._notify_listeners(MarketEvent.TRADE, trade=trade)
        return trade

    def _handle_blockchain_trade_event(self, offer, buyer, original_offer, residual_offer):
        if self.bc_contract:
            trade_id, new_offer_id = trade_offer(self.area.bc, self.bc_contract, offer.real_id,
                                                 offer.energy, buyer)

            if residual_offer is not None:
                if new_offer_id is None:
                    raise InvalidTrade("Blockchain and local residual offers are out of sync")
                residual_offer.id = str(new_offer_id)
                residual_offer.real_id = new_offer_id
                self._notify_listeners(
                    MarketEvent.OFFER_CHANGED,
                    existing_offer=original_offer,
                    new_offer=residual_offer
                )
        else:
            trade_id = str(uuid.uuid4())
        return trade_id, residual_offer

    def _update_stats_after_trade(self, trade, offer, buyer, already_tracked=False):
        # FIXME: The following updates need to be done in response to the BC event
        # TODO: For now event driven blockchain updates have been disabled in favor of a
        # sequential approach, but once event handling is enabled this needs to be handled
        if not already_tracked:
            self.trades.append(trade)
        self._update_accumulated_trade_price_energy(trade)
        self.traded_energy[offer.seller] += offer.energy
        self.traded_energy[buyer] -= offer.energy
        self.ious[buyer][offer.seller] += offer.price
        self._update_min_max_avg_trade_prices(offer.price / offer.energy)
        # Recalculate offer min/max price since offer was removed
        self._update_min_max_avg_offer_prices()

    def _update_accumulated_trade_price_energy(self, trade):
        self.accumulated_trade_price += trade.offer.price
        self.accumulated_trade_energy += trade.offer.energy

    def _update_min_max_avg_offer_prices(self):
        self._avg_offer_price = None
        offer_prices = [o.price / o.energy for o in self.offers.values()]
        if offer_prices:
            self.min_offer_price = round(min(offer_prices), 4)
            self.max_offer_price = round(max(offer_prices), 4)

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
            self.accumulated_trade_energy,
            self.accumulated_trade_price
        )

    @property
    def avg_offer_price(self):
        if self._avg_offer_price is None:
            price = sum(o.price for o in self.offers.values())
            energy = sum(o.energy for o in self.offers.values())
            self._avg_offer_price = round(price / energy, 4) if energy else 0
        return self._avg_offer_price

    @property
    def avg_trade_price(self):
        if self._avg_trade_price is None:
            price = self.accumulated_trade_price
            energy = self.accumulated_trade_energy
            self._avg_trade_price = round(price / energy, 4) if energy else 0
        return self._avg_trade_price

    @property
    def sorted_offers(self):
        return self._sorted_offers

    @property
    def most_affordable_offers(self):
        cheapest_offer = self.sorted_offers[0]
        rate = cheapest_offer.price / cheapest_offer.energy
        return [o for o in self.sorted_offers if
                abs(o.price / o.energy - rate) < OFFER_PRICE_THRESHOLD]

    @property
    def _now(self):
        if self.area:
            return self.area.now
        log.error("No area available. Using real system time!")
        return DateTime.now(tz=TIME_ZONE)

    def set_actual_energy(self, time, reporter, value):
        self.actual_energy[time][reporter] += value
        if reporter in self.accumulated_actual_energy_agg:
            self.accumulated_actual_energy_agg[reporter] += value
        else:
            self.accumulated_actual_energy_agg[reporter] = value

    @property
    def actual_energy_agg(self):
        return self.accumulated_actual_energy_agg

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
            except UnicodeError:
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
            except UnicodeError:
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
            except UnicodeError:
                # Could blow up with certain unicode characters
                pass
        return "\n".join(out)

    def bought_energy(self, buyer):
        return sum(trade.offer.energy for trade in self.trades if trade.buyer == buyer)

    def sold_energy(self, seller):
        return sum(trade.offer.energy for trade in self.trades if trade.offer.seller == seller)

    def total_spent(self, buyer):
        return sum(trade.offer.price for trade in self.trades if trade.buyer == buyer)

    def total_earned(self, seller):
        return sum(trade.offer.price for trade in self.trades if trade.seller == seller)


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


class BalancingMarket(Market):
    def __init__(self, time_slot=None, area=None, notification_listener=None, readonly=False):
        self.unmatched_energy_upward = 0
        self.unmatched_energy_downward = 0
        self.accumulated_supply_balancing_trade_price = 0
        self.accumulated_supply_balancing_trade_energy = 0
        self.accumulated_demand_balancing_trade_price = 0
        self.accumulated_demand_balancing_trade_energy = 0

        Market.__init__(self, time_slot, area, notification_listener, readonly)

    def offer(self, price: float, energy: float, seller: str, balancing_agent: bool=False):
        return self.balancing_offer(price, energy, seller, balancing_agent)

    def balancing_offer(self, price: float, energy: float,
                        seller: str, balancing_agent: bool=False) -> BalancingOffer:
        if seller not in DeviceRegistry.REGISTRY.keys() and not balancing_agent:
            raise DeviceNotInRegistryError(f"Device {seller} "
                                           f"not in registry ({DeviceRegistry.REGISTRY}).")
        if self.readonly:
            raise MarketReadOnlyException()
        if energy == 0:
            raise InvalidOffer()
        offer = BalancingOffer(str(uuid.uuid4()), price, energy, seller, self)
        self.offers[offer.id] = offer
        self._sorted_offers = \
            sorted(self.offers.values(), key=lambda o: o.price / o.energy)
        log.info(f"[BALANCING_OFFER][NEW][{self.time_slot_str}] {offer}")
        self._notify_listeners(MarketEvent.BALANCING_OFFER, offer=offer)
        return offer

    def accept_offer(self, offer_or_id: Union[str, BalancingOffer], buyer: str, *,
                     energy: int = None, time: DateTime = None, price_drop:
                     bool = False) -> BalancingTrade:
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        residual_offer = None
        offer = self.offers.pop(offer_or_id, None)
        self._sorted_offers = sorted(self.offers.values(),
                                     key=lambda o: o.price / o.energy)
        if offer is None:
            raise OfferNotFoundException()
        if (offer.energy > 0 and energy < 0) or (offer.energy < 0 and energy > 0):
            raise InvalidBalancingTradeException("BalancingOffer and energy "
                                                 "are not compatible")
        try:
            if time is None:
                time = self._now
            if energy is not None:
                # Partial trade
                if energy == 0:
                    raise InvalidBalancingTradeException("Energy can not be zero.")
                elif abs(energy) < abs(offer.energy):
                    original_offer = offer
                    accepted_offer = Offer(
                        offer.id,
                        abs((offer.price / offer.energy) * energy),
                        energy,
                        offer.seller,
                        offer.market
                    )
                    residual_energy = (offer.energy - energy)
                    residual_offer = Offer(
                        str(uuid.uuid4()),
                        abs((offer.price / offer.energy) * residual_energy),
                        residual_energy,
                        offer.seller,
                        offer.market
                    )
                    self.offers[residual_offer.id] = residual_offer
                    log.info(f"[BALANCING_OFFER][CHANGED][{self.time_slot_str}] "
                             f"{original_offer} -> {residual_offer}")
                    offer = accepted_offer
                    self._sorted_offers = sorted(self.offers.values(),
                                                 key=lambda o: o.price / o.energy)
                    self._notify_listeners(
                        MarketEvent.BALANCING_OFFER_CHANGED,
                        existing_offer=original_offer,
                        new_offer=residual_offer
                    )
                elif abs(energy) > abs(offer.energy):
                    raise InvalidBalancingTradeException(
                        f"Energy {energy} can't be greater than offered energy {offer}"
                    )
                else:
                    # Requested partial is equal to offered energy - just proceed normally
                    pass
        except Exception:
            # Exception happened - restore offer
            self.offers[offer.id] = offer
            self._sorted_offers = sorted(self.offers.values(),
                                         key=lambda o: o.price / o.energy)
            raise
        trade = BalancingTrade(id=str(uuid.uuid4()), time=time, offer=offer,
                               seller=offer.seller, buyer=buyer,
                               residual=residual_offer, price_drop=price_drop)
        self.trades.append(trade)
        self._update_accumulated_trade_price_energy(trade)
        log.warning(f"[BALANCING_TRADE][{self.time_slot_str}] {trade}")
        self.traded_energy[offer.seller] += offer.energy
        self.traded_energy[buyer] -= offer.energy
        self.ious[buyer][offer.seller] += offer.price
        self._update_min_max_avg_trade_prices(offer.price / offer.energy)
        # Recalculate offer min/max price since offer was removed
        self._update_min_max_avg_offer_prices()
        offer._traded(trade, self)
        self._notify_listeners(MarketEvent.BALANCING_TRADE, trade=trade)
        return trade

    def delete_balancing_offer(self, offer_or_id: Union[str, BalancingOffer]):
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        offer = self.offers.pop(offer_or_id, None)
        self._sorted_offers = sorted(self.offers.values(), key=lambda o: o.price / o.energy)
        self._update_min_max_avg_offer_prices()
        if not offer:
            raise OfferNotFoundException()
        log.info(f"[BALANCING_OFFER][DEL][{self.time_slot_str}] {offer}")
        self._notify_listeners(MarketEvent.BALANCING_OFFER_DELETED, offer=offer)

    def _update_accumulated_trade_price_energy(self, trade):
        if trade.offer.energy > 0:
            self.accumulated_supply_balancing_trade_price += trade.offer.price
            self.accumulated_supply_balancing_trade_energy += trade.offer.energy
        elif trade.offer.energy < 0:
            self.accumulated_demand_balancing_trade_price += trade.offer.price
            self.accumulated_demand_balancing_trade_energy += abs(trade.offer.energy)

    @property
    def avg_supply_balancing_trade_rate(self):
        price = self.accumulated_supply_balancing_trade_price
        energy = self.accumulated_supply_balancing_trade_energy
        return round(price / energy, 4) if energy else 0

    @property
    def avg_demand_balancing_trade_rate(self):
        price = self.accumulated_demand_balancing_trade_price
        energy = self.accumulated_demand_balancing_trade_energy
        return round(price / energy, 4) if energy else 0
