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
from collections import namedtuple
from typing import Dict  # NOQA
from copy import deepcopy
from d3a.models.strategy.area_agents.inter_area_agent import InterAreaAgent  # NOQA
from d3a.models.strategy.area_agents.one_sided_engine import IAAEngine
from d3a.d3a_core.exceptions import BidNotFound, MarketException
from d3a.models.market.market_structures import Bid
from d3a.d3a_core.util import short_offer_bid_log_str

BidInfo = namedtuple('BidInfo', ('source_bid', 'target_bid'))


class TwoSidedPayAsBidEngine(IAAEngine):
    def __init__(self, name: str, market_1, market_2, min_offer_age: int,
                 owner: "InterAreaAgent"):
        super().__init__(name, market_1, market_2, min_offer_age, owner)
        self.forwarded_bids = {}  # type: Dict[str, BidInfo]
        self.bid_trade_residual = {}  # type: Dict[str, Bid]

    def __repr__(self):
        return "<TwoSidedPayAsBidEngine [{s.owner.name}] {s.name} " \
               "{s.markets.source.time_slot:%H:%M}>".format(s=self)

    def _forward_bid(self, bid):
        if bid.buyer == self.markets.target.name and \
           bid.seller == self.markets.source.name:
            return
        if self.owner.name == self.markets.target.name:
            return

        forwarded_bid = self.markets.target.bid(
            price=self.markets.source.fee_class.update_forwarded_bid_with_fee(
                bid.price, bid.original_bid_price),
            energy=bid.energy,
            buyer=self.owner.name,
            seller=self.markets.target.name,
            original_bid_price=bid.original_bid_price,
            buyer_origin=bid.buyer_origin
        )

        self._add_to_forward_bids(bid, forwarded_bid)
        self.owner.log.trace(f"Forwarding bid {bid} to {forwarded_bid}")
        return forwarded_bid

    def _delete_forwarded_bid_entries(self, bid):
        bid_info = self.forwarded_bids.pop(bid.id, None)
        if not bid_info:
            return
        self.forwarded_bids.pop(bid_info.target_bid.id, None)
        self.forwarded_bids.pop(bid_info.source_bid.id, None)

    def tick(self, *, area):
        super().tick(area=area)

        for bid_id, bid in self.markets.source.get_bids().items():
            if bid_id not in self.forwarded_bids and \
                    self.owner.usable_bid(bid) and \
                    self.owner.name != bid.buyer:
                self._forward_bid(bid)

    def delete_forwarded_bids(self, bid_info):
        try:
            self.markets.target.delete_bid(bid_info.target_bid)
        except BidNotFound:
            self.owner.log.trace(f"Bid {bid_info.target_bid.id} not "
                                 f"found in the target market.")
        self._delete_forwarded_bid_entries(bid_info.source_bid)

    def event_bid_traded(self, *, bid_trade):
        bid_info = self.forwarded_bids.get(bid_trade.offer.id)
        if not bid_info:
            return

        if bid_trade.offer.id == bid_info.target_bid.id:
            # Bid was traded in target market, buy in source
            market_bid = self.markets.source.bids[bid_info.source_bid.id]
            assert bid_trade.offer.energy <= market_bid.energy, \
                f"Traded bid on target market has more energy than the market bid."

            source_rate = bid_info.source_bid.price / bid_info.source_bid.energy
            target_rate = bid_info.target_bid.price / bid_info.target_bid.energy
            assert source_rate >= target_rate, \
                f"bid: source_rate ({source_rate}) is not lower than target_rate ({target_rate})"

            trade_rate = (bid_trade.offer.price/bid_trade.offer.energy)

            if bid_trade.offer_bid_trade_info is not None:
                # Adapt trade_offer_info received by the trade to include source market grid fees,
                # which was skipped when accepting the bid during the trade operation.
                updated_trade_offer_info = \
                    self.markets.source.fee_class.propagate_original_offer_info_on_bid_trade(
                        [None, None, *bid_trade.offer_bid_trade_info]
                    )
            else:
                updated_trade_offer_info = bid_trade.offer_bid_trade_info

            trade_offer_info = \
                self.markets.source.fee_class.update_forwarded_bid_trade_original_info(
                    updated_trade_offer_info, market_bid
                )
            self.markets.source.accept_bid(
                bid=market_bid,
                energy=bid_trade.offer.energy,
                seller=self.owner.name,
                already_tracked=False,
                trade_rate=trade_rate,
                trade_offer_info=trade_offer_info,
                seller_origin=bid_trade.seller_origin
            )
            self.delete_forwarded_bids(bid_info)

        elif bid_trade.offer.id == bid_info.source_bid.id:
            # Bid was traded in the source market by someone else
            self.delete_forwarded_bids(bid_info)
        else:
            raise Exception(f"Invalid bid state for IAA {self.owner.name}: "
                            f"traded bid {bid_trade} was not in offered bids tuple {bid_info}")

    def event_bid_deleted(self, *, bid):
        bid_id = bid.id if isinstance(bid, Bid) else bid
        bid_info = self.forwarded_bids.get(bid_id)

        if not bid_info:
            # Deletion doesn't concern us
            return

        if bid_info.source_bid.id == bid_id:
            # Bid in source market of an bid we're already bidding the target market
            # was deleted - also delete in target market
            try:
                self.delete_forwarded_bids(bid_info)
            except MarketException:
                self.owner.log.exception("Error deleting InterAreaAgent bid")
        self._delete_forwarded_bid_entries(bid_info.source_bid)

    def event_bid_split(self, *, market_id, original_bid, accepted_bid, residual_bid):
        market = self.owner._get_market_from_market_id(market_id)
        if market is None:
            return

        if market == self.markets.target and accepted_bid.id in self.forwarded_bids:
            # bid was split in target market, also split the corresponding forwarded bid
            # in the source market

            local_bid = self.forwarded_bids[original_bid.id].source_bid
            original_bid_price = local_bid.original_bid_price \
                if local_bid.original_bid_price is not None else local_bid.price

            local_split_bid, local_residual_bid = \
                self.markets.source.split_bid(local_bid, accepted_bid.energy, original_bid_price)

            #  add the new bids to forwarded_bids
            self._add_to_forward_bids(local_residual_bid, residual_bid)
            self._add_to_forward_bids(local_split_bid, accepted_bid)

        elif market == self.markets.source and accepted_bid.id in self.forwarded_bids:
            # bid in the source market was split, also split the corresponding forwarded bid
            # in the target market
            if not self.owner.usable_bid(accepted_bid) or \
                    self.owner.name == accepted_bid.seller:
                return

            local_bid = self.forwarded_bids[original_bid.id].source_bid

            original_bid_price = local_bid.original_bid_price \
                if local_bid.original_bid_price is not None else local_bid.price

            local_split_bid, local_residual_bid = \
                self.markets.target.split_bid(local_bid, accepted_bid.energy, original_bid_price)

            #  add the new bids to forwarded_bids
            self._add_to_forward_bids(residual_bid, local_residual_bid)
            self._add_to_forward_bids(accepted_bid, local_split_bid)

        else:
            return

        self.owner.log.debug(f"Bid {short_offer_bid_log_str(local_bid)} was split into "
                             f"{short_offer_bid_log_str(local_split_bid)} and "
                             f"{short_offer_bid_log_str(local_residual_bid)}")

    def _add_to_forward_bids(self, source_bid, target_bid):
        bid_info = BidInfo(deepcopy(source_bid), deepcopy(target_bid))
        self.forwarded_bids[source_bid.id] = bid_info
        self.forwarded_bids[target_bid.id] = bid_info
