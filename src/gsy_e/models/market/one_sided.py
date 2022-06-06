"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
from copy import deepcopy
from logging import getLogger
from math import isclose
from typing import Union, Dict, List, Optional, Callable, Tuple

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import Offer, Trade, TradeBidOfferInfo
from gsy_framework.enums import SpotMarketTypeEnum
from pendulum import DateTime

from gsy_e.gsy_e_core.exceptions import (
    InvalidOffer, MarketReadOnlyException, OfferNotFoundException, InvalidTrade, MarketException)
from gsy_e.gsy_e_core.util import short_offer_bid_log_str
from gsy_e.events.event_structures import MarketEvent
from gsy_e.models.market import MarketBase, lock_market_action, GridFee

log = getLogger(__name__)


class OneSidedMarket(MarketBase):
    """Class responsible for dealing with one sided markets.

    The default market type that D3A simulation uses.
    Only devices that supply energy (producers) are able to place offers on the markets.
    """
    def __init__(  # pylint: disable=too-many-arguments
            self, time_slot: Optional[DateTime] = None,
            bc=None, notification_listener: Optional[Callable] = None,
            readonly: bool = False, grid_fee_type=ConstSettings.MASettings.GRID_FEE_TYPE,
            grid_fees: Optional[GridFee] = None, name: Optional[str] = None,
            in_sim_duration: bool = True):
        super().__init__(time_slot, bc, notification_listener, readonly, grid_fee_type,
                         grid_fees, name)

        # If True, the current market slot is included in the expected duration of the simulation
        self.in_sim_duration = in_sim_duration

    def __repr__(self):
        return (
            f"<{self._class_name} {self.time_slot_str}"
            f" offers: {len(self.offers)} (E: {sum(o.energy for o in self.offers.values())} kWh"
            f" V: {sum(o.price for o in self.offers.values())})"
            f" trades: {len(self.trades)} (E: {self.accumulated_trade_energy} kWh,"
            f" V: {self.accumulated_trade_price})>")

    @property
    def _class_name(self) -> str:
        return self.__class__.__name__

    @property
    def _debug_log_market_type_identifier(self) -> str:
        return "[ONE_SIDED]"

    def _update_new_offer_price_with_fee(self, price: float, original_price: float, energy: float):
        """
        Override one sided market private method to abstract away the grid fee calculation
        when placing an offer to a market.
        :param price: Price of the offer coming from the source market, in cents
        :param original_price: Price of the original offer from the device
        :param energy: Energy of the offer
        :return: Updated price for the forwarded offer on this market, in cents
        """
        return self.fee_class.update_incoming_offer_with_fee(
            price / energy, original_price / energy) * energy

    @lock_market_action
    def get_offers(self) -> Dict:
        """
        Retrieves a copy of all open offers of the market. The copy of the offers guarantees
        that the return dict will remain unaffected from any mutations of the market offer list
        that might happen concurrently (more specifically can be used in for loops without raising
        the 'dict changed size during iteration' exception)
        Returns: dict with open offers, offer id as keys, and Offer objects as values

        """
        return deepcopy(self.offers)

    @lock_market_action
    def offer(  # pylint: disable=too-many-arguments, too-many-locals
            self, price: float, energy: float, seller: str, seller_origin: str,
            offer_id: Optional[str] = None,
            original_price: Optional[float] = None,
            dispatch_event: bool = True,
            adapt_price_with_fees: bool = True,
            add_to_history: bool = True,
            seller_origin_id: Optional[str] = None,
            seller_id: Optional[str] = None,
            attributes: Optional[Dict] = None,
            requirements: Optional[List[Dict]] = None,
            time_slot: Optional[DateTime] = None) -> Offer:
        """Post offer inside the market."""

        if self.readonly:
            raise MarketReadOnlyException()
        if energy <= 0:
            raise InvalidOffer()
        if original_price is None:
            original_price = price

        if not time_slot:
            time_slot = self.time_slot

        if adapt_price_with_fees:
            price = self._update_new_offer_price_with_fee(price, original_price, energy)

        if price < 0.0:
            raise MarketException("Negative price after taxes, offer cannot be posted.")

        if offer_id is None:
            offer_id = self.bc_interface.create_new_offer(energy, price, seller)
        offer = Offer(offer_id, self.now, price, energy, seller, original_price,
                      seller_origin=seller_origin, seller_origin_id=seller_origin_id,
                      seller_id=seller_id, attributes=attributes, requirements=requirements,
                      time_slot=time_slot)

        self.offers[offer.id] = offer
        if add_to_history is True:
            self.offer_history.append(offer)

        log.debug("%s[OFFER][NEW][%s][%s] %s",
                  self._debug_log_market_type_identifier, self.name,
                  self.time_slot_str or offer.time_slot, offer)
        if dispatch_event is True:
            self.dispatch_market_offer_event(offer)
        return offer

    def dispatch_market_offer_event(self, offer: Offer) -> None:
        """Dispatch the OFFER event to the listeners."""

        self._notify_listeners(MarketEvent.OFFER, offer=offer)

    @lock_market_action
    def delete_offer(self, offer_or_id: Union[str, Offer]) -> None:
        """Delete the offer from cache and notify listeners."""

        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        offer = self.offers.pop(offer_or_id, None)
        if not offer:
            raise OfferNotFoundException()
        self.bc_interface.cancel_offer(offer)

        log.debug("%s[OFFER][DEL][%s][%s] %s",
                  self._debug_log_market_type_identifier, self.name,
                  self.time_slot_str or offer.time_slot, offer)
        self._notify_listeners(MarketEvent.OFFER_DELETED, offer=offer)

    def _update_offer_fee_and_calculate_final_price(self, energy, trade_rate,
                                                    energy_portion, original_price):
        if self._is_constant_fees:
            fees = self.fee_class.grid_fee_rate * energy
        else:
            fees = self.fee_class.grid_fee_rate * original_price * energy_portion
        return fees, energy * trade_rate

    def split_offer(self, original_offer: Offer, energy: float,
                    orig_offer_price: float) -> Tuple[Offer, Offer]:
        """Split offer into two, one with provided energy, the other with the residual."""

        self.offers.pop(original_offer.id, None)

        # same offer id is used for the new accepted_offer
        original_accepted_price = energy / original_offer.energy * orig_offer_price
        accepted_offer = self.offer(offer_id=original_offer.id,
                                    price=original_offer.price * (energy / original_offer.energy),
                                    energy=energy,
                                    seller=original_offer.seller,
                                    original_price=original_accepted_price,
                                    dispatch_event=False,
                                    seller_origin=original_offer.seller_origin,
                                    seller_origin_id=original_offer.seller_origin_id,
                                    seller_id=original_offer.seller_id,
                                    adapt_price_with_fees=False,
                                    add_to_history=False,
                                    attributes=original_offer.attributes,
                                    requirements=original_offer.requirements,
                                    time_slot=original_offer.time_slot)

        residual_price = (1 - energy / original_offer.energy) * original_offer.price
        residual_energy = original_offer.energy - energy

        original_residual_price = ((original_offer.energy - energy) /
                                   original_offer.energy) * orig_offer_price

        residual_offer = self.offer(price=residual_price,
                                    energy=residual_energy,
                                    seller=original_offer.seller,
                                    original_price=original_residual_price,
                                    dispatch_event=False,
                                    seller_origin=original_offer.seller_origin,
                                    seller_origin_id=original_offer.seller_origin_id,
                                    seller_id=original_offer.seller_id,
                                    adapt_price_with_fees=False,
                                    add_to_history=True,
                                    attributes=original_offer.attributes,
                                    requirements=original_offer.requirements,
                                    time_slot=original_offer.time_slot)

        log.debug("%s[OFFER][SPLIT][%s, %s] (%s into %s and %s",
                  self._debug_log_market_type_identifier,
                  self.time_slot_str or residual_offer.time_slot, self.name,
                  short_offer_bid_log_str(original_offer), short_offer_bid_log_str(accepted_offer),
                  short_offer_bid_log_str(residual_offer))

        self.bc_interface.change_offer(accepted_offer, original_offer, residual_offer)

        self._notify_listeners(
            MarketEvent.OFFER_SPLIT,
            original_offer=original_offer,
            accepted_offer=accepted_offer,
            residual_offer=residual_offer)

        return accepted_offer, residual_offer

    def _determine_offer_price(  # pylint: disable=too-many-arguments
            self, energy_portion, energy, trade_rate,
            trade_bid_info, orig_offer_price):
        if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.ONE_SIDED.value:
            return self._update_offer_fee_and_calculate_final_price(
                energy, trade_rate, energy_portion, orig_offer_price
            )

        _, grid_fee_rate, trade_rate_incl_fees = self.fee_class.calculate_trade_price_and_fees(
                trade_bid_info)
        grid_fee_price = grid_fee_rate * energy
        return grid_fee_price, energy * trade_rate_incl_fees

    @lock_market_action
    def accept_offer(  # pylint: disable=too-many-locals
            self, offer_or_id: Union[str, Offer], buyer: str, *,
            energy: Optional[float] = None,
            already_tracked: bool = False,
            trade_rate: Optional[float] = None,
            trade_bid_info: Optional[TradeBidOfferInfo] = None,
            buyer_origin: Optional[str] = None,
            buyer_origin_id: Optional[str] = None,
            buyer_id: Optional[str] = None) -> Trade:
        """Accept an offer and create a Trade."""

        if self.readonly:
            raise MarketReadOnlyException()

        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        offer = self.offers.pop(offer_or_id, None)
        if offer is None:
            raise OfferNotFoundException()

        if energy is None or isclose(energy, offer.energy, abs_tol=1e-8):
            energy = offer.energy

        original_offer = offer
        residual_offer = None

        if trade_rate is None:
            trade_rate = offer.energy_rate

        orig_offer_price = offer.original_price or offer.price

        try:
            if energy == 0:
                raise InvalidTrade("Energy can not be zero.")
            if energy < offer.energy:
                # partial energy is requested

                accepted_offer, residual_offer = self.split_offer(offer, energy, orig_offer_price)

                fee_price, trade_price = self._determine_offer_price(
                    energy_portion=energy / accepted_offer.energy, energy=energy,
                    trade_rate=trade_rate, trade_bid_info=trade_bid_info,
                    orig_offer_price=orig_offer_price)

                offer = accepted_offer
                offer.update_price(trade_price)

            elif energy > offer.energy:
                raise InvalidTrade(f"Energy ({energy}) can't be greater than "
                                   f"offered energy ({offer.energy})")
            else:
                # Requested energy is equal to offer's energy - just proceed normally
                fee_price, trade_price = self._determine_offer_price(
                    1, energy, trade_rate, trade_bid_info, orig_offer_price)
                offer.update_price(trade_price)
        except Exception:
            # Exception happened - restore offer
            self.offers[offer.id] = offer
            raise

        trade_id, residual_offer = self.bc_interface.handle_blockchain_trade_event(
            offer, buyer, original_offer, residual_offer)

        # Delete the accepted offer from self.offers:
        self.offers.pop(offer.id, None)
        offer_bid_trade_info = self.fee_class.propagate_original_bid_info_on_offer_trade(
            trade_original_info=trade_bid_info)

        trade = Trade(trade_id, self.now, offer, offer.seller, buyer,
                      traded_energy=energy, trade_price=trade_price, residual=residual_offer,
                      offer_bid_trade_info=offer_bid_trade_info,
                      seller_origin=offer.seller_origin, buyer_origin=buyer_origin,
                      fee_price=fee_price, buyer_origin_id=buyer_origin_id,
                      seller_origin_id=offer.seller_origin_id,
                      seller_id=offer.seller_id, buyer_id=buyer_id, time_slot=offer.time_slot
                      )

        self.bc_interface.track_trade_event(self.time_slot, trade)

        if already_tracked is False:
            self._update_stats_after_trade(trade, offer)
            log.info("%s[TRADE][OFFER] [%s] [%s] %s",
                     self._debug_log_market_type_identifier, self.name, trade.time_slot, trade)

        self._notify_listeners(MarketEvent.OFFER_TRADED, trade=trade)
        return trade

    @property
    def type_name(self):
        """Return the market type representation."""
        return "Spot Market"
