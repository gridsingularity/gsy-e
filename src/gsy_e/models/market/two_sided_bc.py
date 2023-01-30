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
import calendar
from logging import getLogger
from typing import Union, Optional, Callable
from pendulum import DateTime

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import TraderDetails

from substrateinterface.exceptions import SubstrateRequestException

from gsy_dex.data_classes import Bid as BcBid
from gsy_dex.gsy_orderbook import GSyOrderbook

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.gsy_e_core.exceptions import (BidNotFoundException,
    NegativePriceOrdersException, NegativeEnergyOrderException, InvalidBid)
from gsy_e.models.market.one_sided_bc import OneSidedBcMarket
from gsy_e.models.market import lock_market_action

log = getLogger(__name__)


class TwoSidedBcMarket(OneSidedBcMarket):
    """Extend One sided market class and add support for bidding functionality.

    A market type that allows producers to place energy offers to the markets
    (exactly the same way as on the one-sided market case), but also allows the consumers
    to place energy bids on their respective markets.
    Contrary to the one sided market, where the offers are selected directly by the consumers,
    the offers and bids are being matched via some matching algorithm.
    """

    def __init__(self, time_slot=None, bc=None, area_uuid=None, notification_listener=None, readonly=False,
                 grid_fee_type=ConstSettings.MASettings.GRID_FEE_TYPE,
                 grid_fees=None, name=None, in_sim_duration=True):
        # pylint: disable=too-many-arguments
        super().__init__(time_slot, bc, area_uuid, notification_listener, readonly, grid_fee_type,
                         grid_fees, name, in_sim_duration=in_sim_duration)
        self.nonce = 1

    @property
    def _debug_log_market_type_identifier(self):
        return "[TWO_SIDED_BC]"

    def __repr__(self):
        return (f"<{self._class_name} {self.time_slot_str} bids: {len(self.bids)}"
                f" (E: {sum(b.energy for b in self.bids.values())} kWh"
                f" V:{sum(b.price for b in self.bids.values())}) "
                f"offers: {len(self.offers)} (E: {sum(o.energy for o in self.offers.values())} kWh"
                f" V: {sum(o.price for o in self.offers.values())}) "
                f"trades: {len(self.trades)} (E: {self.accumulated_trade_energy} kWh"
                f", V: {self.accumulated_trade_price})>")

    @lock_market_action
    def bid(self, price: float, energy: float, buyer: TraderDetails,
            bid_id: Optional[str] = None,
            original_price: Optional[float] = None,
            adapt_price_with_fees: bool = True,
            add_to_history: bool = True,
            dispatch_event: bool = True,
            time_slot: Optional[DateTime] = None) -> BcBid:
        # pylint: disable=too-many-arguments
        if energy <= FLOATING_POINT_TOLERANCE:
            raise NegativeEnergyOrderException("Energy value for bid can not be negative.")

        if not time_slot:
            time_slot = self.time_slot

        if original_price is None:
            original_price = price

        if adapt_price_with_fees:
            price = self.fee_class.update_incoming_bid_with_fee(
                price / energy, original_price / energy) * energy

        if price < 0.0:
            raise NegativePriceOrdersException(
                "Negative price after taxes, bid cannot be posted.")

        bid = BcBid(buyer=self.bc_interface.conn.get_creds_from_area(self.area_uuid), nonce=self.nonce,
                    area_uuid=self.area_uuid, market_uuid=[1], time_slot=calendar.timegm(self.time_slot.timetuple()),
                    attributes=[[1]], energy=energy, price=price, priority=1, energy_type=[1])
        deposited_collateral = self.bc_interface.conn.deposited_collateral.get(self.area_uuid)
        if deposited_collateral is None or deposited_collateral < energy * price:
            self.bc_interface.deposit_collateral(energy * price, self.area_uuid)
        insert_order_call = self.bc_interface.conn.gsy_orderbook.create_insert_orders_call([bid.serializable_order_dict()])
        signed_insert_order_call_extrinsic = self.bc_interface.conn.conn.substrate.create_signed_extrinsic(insert_order_call,
                                                                                              self.bc_interface.get_creds_from_area(self.area_uuid))
        try:
            receipt = self.bc_interface.conn.submit_extrinsic(signed_insert_order_call_extrinsic)
            if receipt.is_success:
                log.debug("post bid succeeded")
                log.debug("%s[BID][NEW][%s][%s] %s",
                          self._debug_log_market_type_identifier, self.name,
                          self.time_slot_str or bid.time_slot, bid)
                self.bids[str(bid.nonce)] = bid
                self.nonce += 1
            else:
                raise InvalidBid
        except SubstrateRequestException as e:
            log.error("Failed to send the extrinsic to the node %s", e)

        if add_to_history is True:
            self.bid_history.append(bid)

        return bid

    @lock_market_action
    def delete_bid(self, bid_or_id: Union[str, BcBid]):
        if isinstance(bid_or_id, BcBid):
            bid_or_id = str(bid_or_id.nonce)
        bid = self.bids.pop(bid_or_id, None)
        if not bid:
            raise BidNotFoundException(bid_or_id)
        remove_order_call = self.bc_interface.gsy_orderbook.create_remove_orders_call([bid.serializable_order_dict()])
        signed_remove_order_call_extrinsic = self.bc_interface.conn.generate_signed_extrinsic(remove_order_call,
                                                                                              self.bc_interface.get_creds_from_area(self.area_uuid))
        try:
            receipt = self.bc_interface.conn.submit_extrinsic(signed_remove_order_call_extrinsic)
            if receipt.is_success:
                log.debug("%s[BID][DEL][%s] %s",
                          self._debug_log_market_type_identifier, self.time_slot_str or bid.time_slot, bid)
            else:
                self.bid[bid_or_id] = bid
                raise InvalidBid
        except SubstrateRequestException as e:
            log.error("Failed to send the extrinsic to the node %s", e)