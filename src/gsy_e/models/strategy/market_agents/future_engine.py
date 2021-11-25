"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange

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
from collections import namedtuple
from typing import Dict

from pendulum import DateTime

from gsy_e.models.strategy.market_agents.two_sided_engine import TwoSidedEngine

BidInfo = namedtuple("BidInfo", ("source_bid", "target_bid"))


class FutureEngine(TwoSidedEngine):
    """Handles order forwarding between future markets."""

    def __repr__(self) -> str:
        return (f"<FutureEngine [{self.owner.name}] {self.name} "
                f"{self.markets.source.time_slot:%H:%M}>")

    @staticmethod
    def _delete_trade_residual_buffers(residual_buffer: Dict,
                                       current_market_slot: DateTime) -> None:
        delete_order_ids = []
        for order in residual_buffer.values():
            if order.time_slot <= current_market_slot:
                delete_order_ids.append(order.id)
                del order
        for order_id in delete_order_ids:
            residual_buffer.pop(order_id, None)

    def clean_up_order_buffers(self, current_market_slot: DateTime) -> None:
        """
        Remove orders from engine buffers that are not connected to a future market any more
        Args:
            current_market_slot: current (not future) market slot

        Returns:

        """
        for buffer in [self.bid_trade_residual, self.trade_residual]:
            self._delete_trade_residual_buffers(buffer, current_market_slot)

        delete_bids = []
        for bid_info in self.forwarded_bids.values():
            if bid_info.target_bid.time_slot <= current_market_slot:
                delete_bids.append(bid_info.target_bid)
                delete_bids.append(bid_info.source_bid)

        for bid in delete_bids:
            self._delete_forwarded_bid_entries(bid)

        delete_offers = []
        for offer_info in self.forwarded_offers.values():
            if offer_info.target_offer.time_slot <= current_market_slot:
                delete_offers.append(offer_info.target_offer)
                delete_offers.append(offer_info.source_offer)
        for offer in delete_offers:
            self._delete_forwarded_offer_entries(offer)
