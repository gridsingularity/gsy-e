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
import uuid
from typing import Union  # noqa
from logging import getLogger
from pendulum import DateTime
from copy import deepcopy

from d3a.events.event_structures import MarketEvent
from d3a.models.market.market_structures import Offer, Trade
from d3a.models.market import Market
from d3a.d3a_core.exceptions import InvalidOffer, MarketReadOnlyException, \
    OfferNotFoundException, InvalidTrade
from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a.models.market.blockchain_interface import MarketBlockchainInterface
from d3a.models.market.grid_fees.base_model import GridFees
from d3a_interface.constants_limits import ConstSettings

log = getLogger(__name__)


class OneSidedMarket(Market):

    def __init__(self, time_slot=None, area=None, notification_listener=None, readonly=False):
        # TODO: remove this reference
        self.area = area
        super().__init__(time_slot, area, notification_listener, readonly)
        self.bc_interface = MarketBlockchainInterface(area)

    def __repr__(self):  # pragma: no cover
        return "<OneSidedMarket{} offers: {} (E: {} kWh V: {}) trades: {} (E: {} kWh, V: {})>"\
            .format(" {}".format(self.time_slot_str),
                    len(self.offers),
                    sum(o.energy for o in self.offers.values()),
                    sum(o.price for o in self.offers.values()),
                    len(self.trades),
                    self.accumulated_trade_energy,
                    self.accumulated_trade_price
                    )

    def balancing_offer(self, price, energy, seller, from_agent):
        assert False

    def _update_new_offer_price_with_fee(self, offer_price, original_offer_price, energy):
        return offer_price \
            + self.transfer_fee_ratio * original_offer_price \
            + self.transfer_fee_const * energy

    def offer(self, price: float, energy: float, seller: str,
              original_offer_price=None, dispatch_event=True, seller_origin=None) -> Offer:
        if self.readonly:
            raise MarketReadOnlyException()
        if energy <= 0:
            raise InvalidOffer()
        if original_offer_price is None:
            original_offer_price = price

        price = self._update_new_offer_price_with_fee(price, original_offer_price, energy)

        offer_id = self.bc_interface.create_new_offer(energy, price, seller)
        offer = Offer(offer_id, price, energy, seller, original_offer_price,
                      seller_origin=seller_origin)

        self.offers[offer.id] = deepcopy(offer)
        self.offer_history.append(offer)
        log.debug(f"[OFFER][NEW][{self.time_slot_str}] {offer}")
        self._update_min_max_avg_offer_prices()
        if dispatch_event is True:
            self.dispatch_market_offer_event(offer)
        return offer

    def dispatch_market_offer_event(self, offer):
        self._notify_listeners(MarketEvent.OFFER, offer=offer)

    def delete_offer(self, offer_or_id: Union[str, Offer]):
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id

        offer = self.offers.pop(offer_or_id, None)

        self.bc_interface.cancel_offer(offer)

        self._update_min_max_avg_offer_prices()
        if not offer:
            raise OfferNotFoundException()
        log.debug(f"[OFFER][DEL][{self.time_slot_str}] {offer}")

        # TODO: Once we add event-driven blockchain, this should be asynchronous
        self._notify_listeners(MarketEvent.OFFER_DELETED, offer=offer)

    def _update_offer_fee_and_calculate_final_price(self, energy, trade_rate,
                                                    energy_portion, original_price):
        fees = self.transfer_fee_ratio * original_price * energy_portion \
            + self.transfer_fee_const * energy
        self.market_fee += fees
        return energy * trade_rate - fees

    @classmethod
    def _calculate_original_prices(cls, offer):
        return offer.original_offer_price \
            if offer.original_offer_price is not None \
            else offer.price

    def accept_offer(self, offer_or_id: Union[str, Offer], buyer: str, *, energy: int = None,
                     time: DateTime = None,
                     already_tracked: bool = False, trade_rate: float = None,
                     trade_bid_info=None, buyer_origin=None) -> Trade:
        if self.readonly:
            raise MarketReadOnlyException()

        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        offer = self.offers.pop(offer_or_id, None)
        if offer is None:
            raise OfferNotFoundException()

        if energy is None:
            energy = offer.energy

        # TODO: can this line be removed due to duplication with line 231 ???
        original_offer = offer
        residual_offer = None

        if trade_rate is None:
            trade_rate = offer.price / offer.energy

        orig_offer_price = self._calculate_original_prices(offer)

        try:
            if time is None:
                time = self._now

            energy_portion = energy / offer.energy
            if energy == 0:
                raise InvalidTrade("Energy can not be zero.")
            # partial energy is requested
            elif energy < offer.energy:
                original_offer = offer
                accepted_offer_id = offer.id \
                    if self.area is None or self.area.bc is None \
                    else offer.real_id

                assert trade_rate + FLOATING_POINT_TOLERANCE >= (offer.price / offer.energy)

                if ConstSettings.IAASettings.MARKET_TYPE == 1:
                    final_price = self._update_offer_fee_and_calculate_final_price(
                        energy, trade_rate, energy_portion, orig_offer_price
                    ) if already_tracked is False else energy * trade_rate
                else:
                    revenue, fees, trade_rate_incl_fees = \
                        GridFees.calculate_trade_price_and_fees(
                            trade_bid_info, self.transfer_fee_ratio
                        )
                    self.market_fee += fees
                    final_price = energy * trade_rate_incl_fees

                accepted_offer = Offer(
                    accepted_offer_id,
                    final_price,
                    energy,
                    offer.seller,
                    seller_origin=offer.seller_origin
                )

                residual_price = (1 - energy_portion) * offer.price
                residual_energy = offer.energy - energy
                original_residual_price = \
                    ((offer.energy - energy) / offer.energy) * orig_offer_price

                residual_offer = Offer(
                    str(uuid.uuid4()),
                    residual_price,
                    residual_energy,
                    offer.seller,
                    original_offer_price=original_residual_price,
                    seller_origin=offer.seller_origin
                )
                self.offers[residual_offer.id] = residual_offer
                log.debug(f"[OFFER][CHANGED][{self.time_slot_str}] "
                          f"{original_offer} -> {residual_offer}")
                offer = accepted_offer

                self.bc_interface.change_offer(offer, original_offer, residual_offer)
                self._notify_listeners(
                    MarketEvent.OFFER_CHANGED,
                    existing_offer=original_offer,
                    new_offer=residual_offer
                )
            elif energy > offer.energy:
                raise InvalidTrade("Energy can't be greater than offered energy")
            else:
                # Requested energy is equal to offer's energy - just proceed normally
                if ConstSettings.IAASettings.MARKET_TYPE == 1:
                    offer.price = self._update_offer_fee_and_calculate_final_price(
                        energy, trade_rate, 1, orig_offer_price
                    ) if already_tracked is False else energy * trade_rate
                else:
                    revenue, fees, trade_price = GridFees.calculate_trade_price_and_fees(
                        trade_bid_info, self.transfer_fee_ratio
                    )
                    self.market_fee += fees
                    offer.price = energy * trade_price

        except Exception:
            # Exception happened - restore offer
            self.offers[offer.id] = offer
            raise

        trade_id, residual_offer = \
            self.bc_interface.handle_blockchain_trade_event(
                offer, buyer, original_offer, residual_offer
            )

        trade = Trade(trade_id, time, offer, offer.seller, buyer, residual_offer,
                      offer_bid_trade_info=GridFees.propagate_original_bid_info_on_offer_trade(
                          trade_bid_info, self.transfer_fee_ratio),
                      seller_origin=offer.seller_origin, buyer_origin=buyer_origin
                      )
        self.bc_interface.track_trade_event(trade)

        if already_tracked is False:
            self._update_stats_after_trade(trade, offer, buyer)
            log.info(f"[TRADE] [{self.time_slot_str}] {trade}")

        # TODO: Use non-blockchain non-event-driven version for now for both blockchain and
        # normal runs.
        self._notify_listeners(MarketEvent.TRADE, trade=trade)
        return trade
