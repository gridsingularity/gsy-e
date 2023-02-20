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
from logging import getLogger
from typing import Union, Optional, Callable

from gsy_dex.data_classes import Offer as BcOffer
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import TraderDetails
from gsy_framework.enums import SpotMarketTypeEnum
from pendulum import DateTime, now
from substrateinterface.exceptions import SubstrateRequestException

from gsy_e.gsy_e_core.exceptions import (
    MarketReadOnlyException, OfferNotFoundException, InvalidOffer)
from gsy_e.models.market import lock_market_action, GridFee
from gsy_e.models.market.two_sided import TwoSidedMarket

log = getLogger(__name__)


class OneSidedBcMarket(TwoSidedMarket):
    """Class responsible for dealing with one sided markets.

    The default market type that D3A simulation uses.
    Only devices that supply energy (producers) are able to place offers on the markets.
    """
    def __init__(  # pylint: disable=too-many-arguments
            self, time_slot: Optional[DateTime] = None,
            bc=None, area_uuid=None, notification_listener: Optional[Callable] = None,
            readonly: bool = False, grid_fee_type=ConstSettings.MASettings.GRID_FEE_TYPE,
            grid_fees: Optional[GridFee] = None, name: Optional[str] = None,
            in_sim_duration: bool = True):
        assert ConstSettings.MASettings.MARKET_TYPE != SpotMarketTypeEnum.COEFFICIENTS.value
        super().__init__(time_slot, bc, notification_listener, readonly, grid_fee_type,
                         grid_fees, name)

        # If True, the current market slot is included in the expected duration of the simulation
        self.in_sim_duration = in_sim_duration
        self.nonce = 1
        self.area_uuid = area_uuid

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
        return "[ONE_SIDED_BC]"

    @lock_market_action
    def offer(  # pylint: disable=too-many-arguments, too-many-locals
            self, price: float, energy: float, seller: TraderDetails,
            offer_id: Optional[str] = None,
            original_price: Optional[float] = None,
            dispatch_event: bool = True,
            adapt_price_with_fees: bool = True,
            add_to_history: bool = True,
            time_slot: Optional[DateTime] = None) -> BcOffer:

        offer = BcOffer(
            seller_keypair=self.bc_interface.conn.get_creds_from_area(self.area_uuid),
            nonce=self.nonce, area_uuid=self.area_uuid, market_uuid=self.id,
            time_slot=self.time_slot, creation_time=now(), seller=seller,
            energy=energy, price=price)
        deposited_collateral = self.bc_interface.conn.deposited_collateral.get(self.area_uuid)
        if deposited_collateral is None or deposited_collateral < energy * price:
            self.bc_interface.conn.deposit_collateral(energy * price, self.area_uuid)
        insert_order_call = self.bc_interface.conn.gsy_orderbook.create_insert_orders_call(
            [offer.serializable_substrate_dict()])
        signed_insert_order_call_extrinsic = self.bc_interface.conn.conn.substrate.create_signed_extrinsic(
            insert_order_call, self.bc_interface.conn.get_creds_from_area(self.area_uuid))
        try:
            receipt = self.bc_interface.conn.conn.submit_extrinsic(
                signed_insert_order_call_extrinsic)
            if receipt.is_success:
                log.debug("post offer succeeded")
                log.debug("%s[OFFER][NEW][%s][%s] %s",
                          self._debug_log_market_type_identifier, self.name,
                          self.time_slot_str or offer.time_slot, offer)
                self.offers[str(offer.nonce)] = offer
                self.nonce += 1
            else:
                raise InvalidOffer
        except SubstrateRequestException as e:
            log.error("Failed to send the extrinsic to the node %s", e)

        return offer

    @lock_market_action
    def delete_offer(self, offer_or_id: Union[str, BcOffer]) -> None:
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, BcOffer):
            offer_or_id = str(offer_or_id.nonce)
        offer = self.offers.pop(offer_or_id, None)
        if not offer:
            raise OfferNotFoundException()
        remove_order_call = self.bc_interface.conn.gsy_orderbook.create_remove_orders_call(
            [offer.serializable_substrate_dict()])
        signed_remove_order_call_extrinsic = self.bc_interface.conn.conn.substrate.create_signed_extrinsic(
            remove_order_call, self.bc_interface.conn.get_creds_from_area(self.area_uuid))
        try:
            receipt = self.bc_interface.conn.conn.submit_extrinsic(signed_remove_order_call_extrinsic)
            if receipt.is_success:
                log.debug("%s[OFFER][NEW][%s][%s] %s",
                          self._debug_log_market_type_identifier, self.name,
                          self.time_slot_str or offer.time_slot, offer)
            else:
                self.offers[offer_or_id] = offer
                raise InvalidOffer
        except SubstrateRequestException as e:
            log.error("Failed to send the extrinsic to the node %s", e)
