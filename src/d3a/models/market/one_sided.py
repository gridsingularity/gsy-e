import uuid
from typing import Dict, List, Set, Union  # noqa
from logging import getLogger
from pendulum import DateTime

from d3a.models.events import MarketEvent
from d3a.models.market.market_structures import Offer, Trade
from d3a.models.market import Market
from d3a.exceptions import InvalidOffer, MarketReadOnlyException, OfferNotFoundException, \
    InvalidTrade
from d3a.blockchain_utils import create_new_offer, cancel_offer

log = getLogger(__name__)


class OneSidedMarket(Market):

    def __init__(self, time_slot=None, area=None, notification_listener=None, readonly=False):
        super().__init__(time_slot, area, notification_listener, readonly)

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
