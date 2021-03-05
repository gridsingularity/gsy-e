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
from typing import Union  # noqa
from logging import getLogger
from pendulum import DateTime

from d3a.events.event_structures import MarketEvent
from d3a.models.market.market_structures import Offer, Trade
from d3a.models.market import Market, lock_market_action
from d3a.d3a_core.exceptions import InvalidOffer, MarketReadOnlyException, \
    OfferNotFoundException, InvalidTrade, MarketException
from d3a.d3a_core.util import short_offer_bid_log_str
from d3a_interface.constants_limits import ConstSettings

log = getLogger(__name__)


class OneSidedMarket(Market):

    def __init__(self, time_slot=None, bc=None, notification_listener=None,
                 readonly=False, grid_fee_type=ConstSettings.IAASettings.GRID_FEE_TYPE,
                 grid_fees=None, name=None, in_sim_duration=True):
        super().__init__(time_slot, bc, notification_listener, readonly, grid_fee_type,
                         grid_fees, name)
        self.in_sim_duration = in_sim_duration

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
        """
        Override one sided market private method to abstract away the grid fee calculation
        when placing an offer to a market.
        :param offer_price: Price of the offer coming from the source market, in cents
        :param original_offer_price: Price of the original offer from the device
        :param energy: Energy of the offer
        :return: Updated price for the forwarded offer on this market, in cents
        """
        return self.fee_class.update_incoming_offer_with_fee(
            offer_price / energy, original_offer_price / energy
        ) * energy

    @lock_market_action
    def get_offers(self):
        return self.offers

    @lock_market_action
    def offer(self, price: float, energy: float, seller: str, seller_origin,
              offer_id=None, original_offer_price=None, dispatch_event=True,
              adapt_price_with_fees=True, add_to_history=True, seller_origin_id=None,
              seller_id=None) -> Offer:
        if self.readonly:
            raise MarketReadOnlyException()
        if energy <= 0:
            raise InvalidOffer()
        if original_offer_price is None:
            original_offer_price = price

        if adapt_price_with_fees:
            price = self._update_new_offer_price_with_fee(price, original_offer_price, energy)

        if price < 0.0:
            raise MarketException("Negative price after taxes, offer cannot be posted.")

        if offer_id is None:
            offer_id = self.bc_interface.create_new_offer(energy, price, seller)
        offer = Offer(offer_id, self.now, price, energy, seller, original_offer_price,
                      seller_origin=seller_origin, seller_origin_id=seller_origin_id,
                      seller_id=seller_id)

        self.offers[offer.id] = offer
        if add_to_history is True:
            self.offer_history.append(offer)
            self._update_min_max_avg_offer_prices()

        log.debug(f"[OFFER][NEW][{self.name}][{self.time_slot_str}] {offer}")
        if dispatch_event is True:
            self.dispatch_market_offer_event(offer)
        return offer

    def dispatch_market_offer_event(self, offer):
        self._notify_listeners(MarketEvent.OFFER, offer=offer)

    @lock_market_action
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
        log.debug(f"[OFFER][DEL][{self.name}][{self.time_slot_str}] {offer}")
        # TODO: Once we add event-driven blockchain, this should be asynchronous
        self._notify_listeners(MarketEvent.OFFER_DELETED, offer=offer)

    def _update_offer_fee_and_calculate_final_price(self, energy, trade_rate,
                                                    energy_portion, original_price):
        if self._is_constant_fees:
            fees = self.fee_class.grid_fee_rate * energy
        else:
            fees = self.fee_class.grid_fee_rate * original_price * energy_portion
        return fees, energy * trade_rate

    @classmethod
    def _calculate_original_prices(cls, offer):
        return offer.original_offer_price \
            if offer.original_offer_price is not None \
            else offer.price

    def split_offer(self, original_offer, energy, orig_offer_price):

        self.offers.pop(original_offer.id, None)
        # same offer id is used for the new accepted_offer
        original_accepted_price = energy / original_offer.energy * orig_offer_price
        accepted_offer = self.offer(offer_id=original_offer.id,
                                    price=original_offer.price * (energy / original_offer.energy),
                                    energy=energy,
                                    seller=original_offer.seller,
                                    original_offer_price=original_accepted_price,
                                    dispatch_event=False,
                                    seller_origin=original_offer.seller_origin,
                                    seller_origin_id=original_offer.seller_origin_id,
                                    seller_id=original_offer.seller_id,
                                    adapt_price_with_fees=False,
                                    add_to_history=False)

        residual_price = (1 - energy / original_offer.energy) * original_offer.price
        residual_energy = original_offer.energy - energy

        original_residual_price = \
            ((original_offer.energy - energy) / original_offer.energy) * orig_offer_price

        residual_offer = self.offer(price=residual_price,
                                    energy=residual_energy,
                                    seller=original_offer.seller,
                                    original_offer_price=original_residual_price,
                                    dispatch_event=False,
                                    seller_origin=original_offer.seller_origin,
                                    seller_origin_id=original_offer.seller_origin_id,
                                    seller_id=original_offer.seller_id,
                                    adapt_price_with_fees=False,
                                    add_to_history=True)

        log.debug(f"[OFFER][SPLIT][{self.time_slot_str}, {self.name}] "
                  f"({short_offer_bid_log_str(original_offer)} into "
                  f"{short_offer_bid_log_str(accepted_offer)} and "
                  f"{short_offer_bid_log_str(residual_offer)}")

        self.bc_interface.change_offer(accepted_offer, original_offer, residual_offer)

        self._notify_listeners(
            MarketEvent.OFFER_SPLIT,
            original_offer=original_offer,
            accepted_offer=accepted_offer,
            residual_offer=residual_offer)

        return accepted_offer, residual_offer

    def determine_offer_price(self, energy_portion, energy, trade_rate,
                              trade_bid_info, orig_offer_price):
        if ConstSettings.IAASettings.MARKET_TYPE == 1:
            return self._update_offer_fee_and_calculate_final_price(
                energy, trade_rate, energy_portion, orig_offer_price
            )
        else:
            revenue, grid_fee_rate, trade_rate_incl_fees = \
                self.fee_class.calculate_trade_price_and_fees(
                    trade_bid_info
                )
            grid_fee_price = grid_fee_rate * energy
            return grid_fee_price, energy * trade_rate_incl_fees

    @lock_market_action
    def accept_offer(self, offer_or_id: Union[str, Offer], buyer: str, *, energy: int = None,
                     time: DateTime = None,
                     already_tracked: bool = False, trade_rate: float = None,
                     trade_bid_info=None, buyer_origin=None, buyer_origin_id=None,
                     buyer_id=None) -> Trade:
        if self.readonly:
            raise MarketReadOnlyException()

        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        offer = self.offers.pop(offer_or_id, None)
        if offer is None:
            raise OfferNotFoundException()

        if energy is None:
            energy = offer.energy

        original_offer = offer
        residual_offer = None

        if trade_rate is None:
            trade_rate = offer.energy_rate

        orig_offer_price = self._calculate_original_prices(offer)

        try:
            if time is None:
                time = self.now

            if energy == 0:
                raise InvalidTrade("Energy can not be zero.")
            elif energy < offer.energy:
                # partial energy is requested

                accepted_offer, residual_offer = self.split_offer(offer, energy, orig_offer_price)

                fee_price, trade_price = self.determine_offer_price(
                    energy_portion=energy / accepted_offer.energy, energy=energy,
                    trade_rate=trade_rate, trade_bid_info=trade_bid_info,
                    orig_offer_price=orig_offer_price)

                offer = accepted_offer
                offer.update_price(trade_price)

            elif energy > offer.energy:
                raise InvalidTrade("Energy can't be greater than offered energy")
            else:
                # Requested energy is equal to offer's energy - just proceed normally
                fee_price, trade_price = self.determine_offer_price(
                    1, energy, trade_rate, trade_bid_info, orig_offer_price)
                offer.update_price(trade_price)
        except Exception:
            # Exception happened - restore offer
            self.offers[offer.id] = offer
            raise

        trade_id, residual_offer = \
            self.bc_interface.handle_blockchain_trade_event(
                offer, buyer, original_offer, residual_offer
            )

        # Delete the accepted offer from self.offers:
        self.offers.pop(offer.id, None)
        offer_bid_trade_info = self.fee_class.propagate_original_bid_info_on_offer_trade(
            trade_original_info=trade_bid_info)
        trade = Trade(trade_id, time, offer, offer.seller, buyer, residual_offer,
                      offer_bid_trade_info=offer_bid_trade_info,
                      seller_origin=offer.seller_origin, buyer_origin=buyer_origin,
                      fee_price=fee_price, buyer_origin_id=buyer_origin_id,
                      seller_origin_id=offer.seller_origin_id,
                      seller_id=offer.seller_id, buyer_id=buyer_id
                      )
        self.bc_interface.track_trade_event(trade)

        if already_tracked is False:
            self._update_stats_after_trade(trade, offer)
            log.info(f"[TRADE] [{self.name}] [{self.time_slot_str}] {trade}")

        # TODO: Use non-blockchain non-event-driven version for now for both blockchain and
        # normal runs.
        self._notify_listeners(MarketEvent.TRADE, trade=trade)
        return trade
