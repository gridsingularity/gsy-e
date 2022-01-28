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
from collections import namedtuple
from typing import Dict, TYPE_CHECKING

from gsy_framework.data_classes import Bid

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.gsy_e_core.exceptions import BidNotFoundException, MarketException
from gsy_e.gsy_e_core.util import short_offer_bid_log_str
from gsy_e.models.strategy.market_agents.one_sided_engine import MAEngine

if TYPE_CHECKING:
    from gsy_e.models.strategy.market_agents.market_agent import MarketAgent

BidInfo = namedtuple("BidInfo", ("source_bid", "target_bid"))


class TwoSidedEngine(MAEngine):
    """Handle forwarding offers and bids to the connected two-sided market."""
    # pylint: disable = too-many-arguments

    def __init__(self, name: str, market_1, market_2, min_offer_age: int, min_bid_age: int,
                 owner: "MarketAgent"):
        super().__init__(name, market_1, market_2, min_offer_age, owner)
        self.forwarded_bids: Dict[str, BidInfo] = {}
        self.bid_trade_residual: Dict[str, Bid] = {}
        self.min_bid_age = min_bid_age
        self.bid_age: Dict[str, int] = {}

    def __repr__(self):
        return "<TwoSidedPayAsBidEngine [{s.owner.name}] {s.name} " \
               "{s.markets.source.time_slot:%H:%M}>".format(s=self)

    def _forward_bid(self, bid):
        if bid.buyer == self.markets.target.name:
            return None

        if bid.price < 0.0:
            self.owner.log.debug("Bid is not forwarded because price < 0")
            return None
        try:
            forwarded_bid = self.markets.target.bid(
                price=(self.markets.source.fee_class.update_forwarded_bid_with_fee(
                    bid.energy_rate, bid.original_price / bid.energy)) * bid.energy,
                energy=bid.energy,
                buyer=self.owner.name,
                original_price=bid.original_price,
                buyer_origin=bid.buyer_origin,
                buyer_origin_id=bid.buyer_origin_id,
                buyer_id=self.owner.uuid,
                time_slot=bid.time_slot
            )
        except MarketException:
            self.owner.log.debug("Bid is not forwarded because grid fees of the target market "
                                 "lead to a negative bid price.")
            return None

        self._add_to_forward_bids(bid, forwarded_bid)
        self.owner.log.trace(f"Forwarding bid {bid} to {forwarded_bid}")
        return forwarded_bid

    def _delete_forwarded_bid_entries(self, bid):
        bid_info = self.forwarded_bids.pop(bid.id, None)
        if not bid_info:
            return
        self.forwarded_bids.pop(bid_info.target_bid.id, None)
        self.forwarded_bids.pop(bid_info.source_bid.id, None)
        self.bid_age.pop(bid_info.source_bid.id, None)
        self.bid_age.pop(bid_info.target_bid.id, None)

    def _should_forward_bid(self, bid, current_tick):

        if bid.id in self.forwarded_bids:
            return False

        if not self.owner.usable_bid(bid):
            return False

        if self.owner.name == bid.buyer:
            return False

        if current_tick - self.bid_age[bid.id] < self.min_bid_age:
            return False

        return True

    # pylint: disable=unused-argument
    def tick(self, *, area):
        super().tick(area=area)

        for bid in self.markets.source.get_bids().values():
            if bid.id not in self.bid_age:
                self.bid_age[bid.id] = area.current_tick

            if self._should_forward_bid(bid, area.current_tick):
                self._forward_bid(bid)

    def _delete_forwarded_bids(self, bid_info):
        try:
            self.markets.target.delete_bid(bid_info.target_bid)
        except BidNotFoundException:
            self.owner.log.trace(f"Bid {bid_info.target_bid.id} not "
                                 f"found in the target market.")
        self._delete_forwarded_bid_entries(bid_info.source_bid)

    def event_bid_traded(self, *, bid_trade):
        """Perform actions that need to be done when BID_TRADED event is triggered."""
        bid_info = self.forwarded_bids.get(bid_trade.offer_bid.id)
        if not bid_info:
            return

        if bid_trade.offer_bid.id == bid_info.target_bid.id:
            # Bid was traded in target market, buy in source
            market_bid = self.markets.source.bids[bid_info.source_bid.id]
            assert bid_trade.offer_bid.energy <= market_bid.energy, \
                "Traded bid on target market has more energy than the market bid."

            source_rate = bid_info.source_bid.energy_rate
            target_rate = bid_info.target_bid.energy_rate
            assert abs(source_rate) + FLOATING_POINT_TOLERANCE >= abs(target_rate), \
                f"bid: source_rate ({source_rate}) is not lower than target_rate ({target_rate})"

            trade_rate = (bid_trade.offer_bid.price/bid_trade.offer_bid.energy)

            if bid_trade.offer_bid_trade_info is not None:
                # Adapt trade_offer_info received by the trade to include source market grid fees,
                # which was skipped when accepting the bid during the trade operation.
                updated_trade_offer_info = \
                    self.markets.source.fee_class.propagate_original_offer_info_on_bid_trade(
                        bid_trade.offer_bid_trade_info
                    )
            else:
                updated_trade_offer_info = bid_trade.offer_bid_trade_info

            trade_offer_info = \
                self.markets.source.fee_class.update_forwarded_bid_trade_original_info(
                    updated_trade_offer_info, market_bid
                )
            self.markets.source.accept_bid(
                bid=market_bid,
                energy=bid_trade.offer_bid.energy,
                seller=self.owner.name,
                already_tracked=False,
                trade_rate=trade_rate,
                trade_offer_info=trade_offer_info,
                seller_origin=bid_trade.seller_origin,
                seller_origin_id=bid_trade.seller_origin_id,
                seller_id=self.owner.uuid
            )
            self._delete_forwarded_bids(bid_info)
            self.bid_age.pop(bid_info.source_bid.id, None)

        elif bid_trade.offer_bid.id == bid_info.source_bid.id:
            # Bid was traded in the source market by someone else
            self._delete_forwarded_bids(bid_info)
            self.bid_age.pop(bid_info.source_bid.id, None)
        else:
            raise Exception(f"Invalid bid state for MA {self.owner.name}: "
                            f"traded bid {bid_trade} was not in offered bids tuple {bid_info}")

    def event_bid_deleted(self, *, bid):
        """Perform actions that need to be done when BID_DELETED event is triggered."""
        bid_id = bid.id if isinstance(bid, Bid) else bid
        bid_info = self.forwarded_bids.get(bid_id)

        if not bid_info:
            # Deletion doesn't concern us
            return

        if bid_info.source_bid.id == bid_id:
            # Bid in source market of an bid we're already bidding the target market
            # was deleted - also delete in target market
            try:
                self._delete_forwarded_bids(bid_info)
            except MarketException:
                self.owner.log.exception("Error deleting MarketAgent bid")
        self._delete_forwarded_bid_entries(bid_info.source_bid)
        self.bid_age.pop(bid_info.source_bid.id, None)

    def event_bid_split(self, *, market_id: str, original_bid: Bid,
                        accepted_bid: Bid, residual_bid: Bid) -> None:
        """Perform actions that need to be done when BID_SPLIT event is triggered."""
        market = self.owner.get_market_from_market_id(market_id)
        if market is None:
            return

        if market == self.markets.target and accepted_bid.id in self.forwarded_bids:
            # bid was split in target market, also split the corresponding forwarded bid
            # in the source market

            local_bid = self.forwarded_bids[original_bid.id].source_bid
            original_price = local_bid.original_price \
                if local_bid.original_price is not None else local_bid.price

            local_split_bid, local_residual_bid = \
                self.markets.source.split_bid(local_bid, accepted_bid.energy, original_price)

            #  add the new bids to forwarded_bids
            self._add_to_forward_bids(local_residual_bid, residual_bid)
            self._add_to_forward_bids(local_split_bid, accepted_bid)

            self.bid_age[local_residual_bid.id] = self.bid_age.pop(local_bid.id)

        elif market == self.markets.source and accepted_bid.id in self.forwarded_bids:
            # bid in the source market was split, also split the corresponding forwarded bid
            # in the target market
            if not self.owner.usable_bid(accepted_bid):
                return

            local_bid = self.forwarded_bids[original_bid.id].source_bid

            original_price = local_bid.original_price \
                if local_bid.original_price is not None else local_bid.price

            local_split_bid, local_residual_bid = \
                self.markets.target.split_bid(local_bid, accepted_bid.energy, original_price)

            #  add the new bids to forwarded_bids
            self._add_to_forward_bids(residual_bid, local_residual_bid)
            self._add_to_forward_bids(accepted_bid, local_split_bid)

            self.bid_age[residual_bid.id] = self.bid_age.pop(original_bid.id)

        else:
            return

        self.owner.log.debug(f"Bid {short_offer_bid_log_str(local_bid)} was split into "
                             f"{short_offer_bid_log_str(local_split_bid)} and "
                             f"{short_offer_bid_log_str(local_residual_bid)}")

    def _add_to_forward_bids(self, source_bid, target_bid):
        bid_info = BidInfo(source_bid, target_bid)
        self.forwarded_bids[source_bid.id] = bid_info
        self.forwarded_bids[target_bid.id] = bid_info
