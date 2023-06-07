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
import uuid
from logging import getLogger
from typing import Union, Optional, Callable

from gsy_dex.data_classes import Offer as BcOffer, float_to_uint
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
    """
    A one-sided blockchain market.

    This class implements a one-sided blockchain market, inheriting from TwoSidedMarket.

    Only devices that supply energy (producers) are able to place offers on the markets.

    Attributes:
    - in_sim_duration (bool): A boolean indicating whether the current market slot is included in
        the expected duration of the simulation.
    - area_uuid (str): A string representing the area UUID of the market.
    """

    def __init__(self, time_slot: Optional[DateTime] = None, bc=None, area_uuid=None,
                 notification_listener: Optional[Callable] = None, readonly: bool = False,
                 grid_fee_type=ConstSettings.MASettings.GRID_FEE_TYPE,
                 grid_fees: Optional[GridFee] = None, name: Optional[str] = None,
                 in_sim_duration: bool = True):
        # pylint: disable=too-many-arguments
        """
        Initialize the OneSidedBcMarket object.

        Args:
        - time_slot (Optional[DateTime], optional): A datetime object representing the time
            slot of the market. Defaults to None.
        - bc (optional): The blockchain interface used to interact with the blockchain.
            Defaults to None.
        - area_uuid: A string representing the area UUID of the market. Defaults to None.
        - notification_listener (Optional[Callable], optional): A callable object that will be
            notified when new trades occur. Defaults to None.
        - readonly (bool): A flag that indicates whether the market is read-only or not.
            Defaults to False.
        - grid_fee_type: A parameter representing grid fee type.
            Defaults to ConstSettings.MASettings.GRID_FEE_TYPE.
        - grid_fees (Optional[GridFee], optional): A parameter representing grid fees.
            Defaults to None.
        - name (Optional[str], optional): A string representing the name of the market.
            Defaults to None.
        - in_sim_duration (bool): A boolean indicating whether the current market slot
            is included in the expected duration of the simulation. Defaults to True.

        Raises:
        - AssertionError: If ConstSettings.MASettings.MARKET_TYPE equals
            SpotMarketTypeEnum.COEFFICIENTS.value.
        """
        assert ConstSettings.MASettings.MARKET_TYPE != SpotMarketTypeEnum.COEFFICIENTS.value
        super().__init__(time_slot, bc, notification_listener, readonly, grid_fee_type,
                         grid_fees, name)

        self.in_sim_duration = in_sim_duration
        self.area_uuid = area_uuid

    def __repr__(self):
        """
        Return a string representation of the OneSidedBcMarket object.

        Returns:
            str: A string representation of the OneSidedBcMarket object.
        """
        return (
            f"<{self._class_name} {self.time_slot_str}"
            f" offers: {len(self.offers)} (E: {sum(o.energy for o in self.offers.values())} kWh"
            f" V: {sum(o.price for o in self.offers.values())})"
            f" trades: {len(self.trades)} (E: {self.accumulated_trade_energy} kWh,"
            f" V: {self.accumulated_trade_price})>")

    @property
    def _class_name(self) -> str:
        """Return the name of the class.

        Returns:
            str: The name of the class.
        """
        return self.__class__.__name__

    @property
    def _debug_log_market_type_identifier(self) -> str:
        """
        Return a string identifying the market type for"""

        return "[ONE_SIDED_BC]"

    @lock_market_action
    def offer(  # pylint: disable=too-many-arguments, too-many-locals
            self, price: float, energy: float, seller: TraderDetails,
            offer_id: Optional[str] = None, original_price: Optional[float] = None,
            dispatch_event: bool = True, adapt_price_with_fees: bool = True,
            add_to_history: bool = True, time_slot: Optional[DateTime] = None) -> BcOffer:
        """
        Post an offer to the DEX orderbook.

        Args:
        - price (float): The price of the offer.
        - energy (float): The amount of energy for the offer.
        - seller (TraderDetails): The details of the seller.
        - offer_id (Optional[str], optional): The ID of the offer.
            Defaults to None.
        - original_price (Optional[float], optional): The original price of the offer.
            Defaults to None.
        - dispatch_event (bool, optional): Whether to dispatch an event.
            Defaults to True.
        - adapt_price_with_fees (bool, optional): Whether to adapt the price with fees.
            Defaults to True.
        - add_to_history (bool, optional): Whether to add the offer to the history.
            Defaults to True.
        - time_slot (Optional[DateTime], optional): The time slot of the offer.
            Defaults to None.

        Returns:
        - BcOffer: The created offer.

        Raises:
        - InvalidOffer: If the offer is invalid.
        - SubstrateRequestException: If there's an issue with the substrate request.
        """
        if offer_id is None:
            offer_id = str(uuid.uuid4())
        offer = BcOffer(  # pylint: disable=unexpected-keyword-arg
            seller_keypair=self.bc_interface.conn.get_creds_from_area(self.area_uuid),
            seller=seller, id=offer_id, area_uuid=self.area_uuid, market_uuid=self.id,
            time_slot=self.time_slot, creation_time=now(), energy=energy, price=price)
        deposited_collateral = self.bc_interface.conn.deposited_collateral.get(self.area_uuid)
        if (deposited_collateral is None or
            deposited_collateral < float_to_uint(energy) * float_to_uint(price)) \
                and float_to_uint(energy) * float_to_uint(price) > 0:
            self.bc_interface.conn.deposit_collateral(
                float_to_uint(energy) * float_to_uint(price), self.area_uuid)
        insert_order_call = self.bc_interface.conn.gsy_orderbook.create_insert_orders_call(
            [offer.serializable_substrate_dict()])
        signed_insert_order_call_extrinsic = \
            self.bc_interface.conn.conn.substrate.create_signed_extrinsic(
                insert_order_call, self.bc_interface.conn.get_creds_from_area(self.area_uuid))
        try:
            receipt = self.bc_interface.conn.conn.submit_extrinsic(
                signed_insert_order_call_extrinsic)
            if receipt.is_success:
                log.debug("post offer succeeded")
                log.debug("%s[OFFER][NEW][%s][%s] %s",
                          self._debug_log_market_type_identifier, self.name,
                          self.time_slot_str or offer.time_slot, offer)
                self.offers[str(offer.id)] = offer
            else:
                raise InvalidOffer
        except SubstrateRequestException as e:
            log.error("Failed to send the extrinsic to the node %s", e)

        return offer

    @lock_market_action
    def delete_offer(self, offer_or_id: Union[str, BcOffer]) -> None:
        """
        Delete the offer identified by offer_or_id from the DEX orderbook.

        Args:
        - offer_or_id (Union[str, BcOffer]): The offer ID to be deleted, or the offer itself.

        Returns:
        - None

        Raises:
        - MarketReadOnlyException: If the market is read-only and cannot be modified.
        - OfferNotFoundException: If the offer ID is not found in the market.
        - InvalidOffer: If the offer deletion transaction fails.
        """
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, BcOffer):
            offer_or_id = str(offer_or_id.id)
        offer = self.offers.pop(offer_or_id, None)
        if not offer:
            raise OfferNotFoundException()
        offer = self.bc_interface.conn.update_offer_nonce(offer, self.area_uuid)
        if not offer.nonce:
            raise InvalidOffer
        remove_order_call = self.bc_interface.conn.gsy_orderbook.create_remove_orders_call(
            [offer.nonce])
        signed_remove_order_call_extrinsic = \
            self.bc_interface.conn.conn.substrate.create_signed_extrinsic(
                remove_order_call, self.bc_interface.conn.get_creds_from_area(self.area_uuid))
        try:
            receipt = self.bc_interface.conn.conn.submit_extrinsic(
                signed_remove_order_call_extrinsic)
            if receipt.is_success:
                log.debug("%s[OFFER][NEW][%s][%s] %s",
                          self._debug_log_market_type_identifier, self.name,
                          self.time_slot_str or offer.time_slot, offer)
            else:
                raise InvalidOffer
        except SubstrateRequestException as e:
            log.error("Failed to send the extrinsic to the node %s", e)
