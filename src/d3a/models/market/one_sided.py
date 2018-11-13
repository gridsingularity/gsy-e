import uuid
from typing import Union  # noqa
from logging import getLogger
from pendulum import DateTime

from d3a.events.event_structures import MarketEvent
from d3a.models.market.market_structures import Offer, Trade
from d3a.models.market import Market
from d3a.models.market.blockchain_interface import MarketBlockchainInterface
from d3a.d3a_core.exceptions import InvalidOffer, MarketReadOnlyException, \
    OfferNotFoundException, InvalidTrade

log = getLogger(__name__)


class OneSidedMarket(Market):

    def __init__(self, time_slot=None, area=None, notification_listener=None, readonly=False):
        self.area = area
        super().__init__(time_slot, area, notification_listener, readonly)
        self.bc_interface = MarketBlockchainInterface(area)

    def __repr__(self):  # pragma: no cover
        return "<OneSidedMarket{} offers: {} (E: {} kWh V: {}) trades: {} (E: {} kWh, V: {})>"\
            .format(" {:%H:%M}".format(self.time_slot) if self.time_slot else "",
                    len(self.offers),
                    sum(o.energy for o in self.offers.values()),
                    sum(o.price for o in self.offers.values()),
                    len(self.trades),
                    self.accumulated_trade_energy,
                    self.accumulated_trade_price
                    )

    def balancing_offer(self, price, energy, seller, from_agent):
        assert False

    def offer(self, price: float, energy: float, seller: str) -> Offer:
        if self.readonly:
            raise MarketReadOnlyException()
        if energy <= 0:
            raise InvalidOffer()

        offer_id = self.bc_interface.create_new_offer(energy, price, seller)
        offer = Offer(offer_id, price, energy, seller, self)
        self.offers[offer.id] = offer
        self._sorted_offers = sorted(self.offers.values(), key=lambda o: o.price / o.energy)
        self.offer_history.append(offer)
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

        self.bc_interface.cancel_offer(offer)

        self._sorted_offers = sorted(self.offers.values(), key=lambda o: o.price / o.energy)
        self._update_min_max_avg_offer_prices()
        if not offer:
            raise OfferNotFoundException()
        log.info(f"[OFFER][DEL][{self.time_slot_str}] {offer}")

        # TODO: Once we add event-driven blockchain, this should be asynchronous
        self._notify_listeners(MarketEvent.OFFER_DELETED, offer=offer)

    def accept_offer(self, offer_or_id: Union[str, Offer], buyer: str, *, energy: int = None,
                     time: DateTime = None, price_drop: bool = False,
                     clear_rate: int = None) -> Trade:
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
                    if clear_rate is not None:
                        energy_rate = clear_rate
                    else:
                        energy_rate = offer.price / offer.energy

                    accepted_offer = Offer(
                        accepted_offer_id,
                        energy_rate * energy,
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

                    self.bc_interface.change_offer(offer, original_offer, residual_offer)
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

        trade_id, residual_offer = \
            self.bc_interface.handle_blockchain_trade_event(
                offer, buyer, original_offer, residual_offer
            )
        trade = Trade(trade_id, time, offer, offer.seller, buyer, residual_offer, price_drop)
        self.bc_interface.track_trade_event(trade)

        self._update_stats_after_trade(trade, offer, buyer)
        log.warning(f"[TRADE][{self.time_slot_str}] {trade}")

        # FIXME: Needs to be triggered by blockchain event
        # TODO: Same as above, should be modified when event-driven blockchain is introduced
        offer._traded(trade, self)

        # TODO: Use non-blockchain non-event-driven version for now for both blockchain and
        # normal runs.
        self._notify_listeners(MarketEvent.TRADE, trade=trade)
        return trade
