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
from d3a.models.strategy.area_agents.one_sided_engine import IAAEngine
from d3a.d3a_core.exceptions import BidNotFound, MarketException
from d3a.models.market.market_structures import Bid

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
        if bid.buyer == self.markets.target.area.name and \
           bid.seller == self.markets.source.area.name:
            return
        if self.owner.name == self.markets.target.area.name:
            return
        forwarded_bid = self.markets.target.bid(
            bid.price,
            bid.energy,
            self.owner.name,
            self.markets.target.area.name,
            original_bid_price=bid.original_bid_price,
            source_market=self.markets.source
        )
        bid_coupling = BidInfo(bid, forwarded_bid)
        self.forwarded_bids[forwarded_bid.id] = bid_coupling
        self.forwarded_bids[bid.id] = bid_coupling
        self.owner.log.debug(f"Forwarding bid {bid} to {forwarded_bid}")
        return forwarded_bid

    def _perform_pay_as_bid_matching(self):
        # Pay as bid first
        # There are 2 simplistic approaches to the problem
        # 1. Match the cheapest offer with the most expensive bid. This will favor the sellers
        # 2. Match the cheapest offer with the cheapest bid. This will favor the buyers,
        #    since the most affordable offers will be allocated for the most aggressive buyers.

        # Sorted bids in descending order
        sorted_bids = list(reversed(sorted(
            self.markets.source.bids.values(),
            key=lambda b: b.price / b.energy))
        )

        # Sorted offers in descending order
        sorted_offers = list(reversed(sorted(
            self.markets.source.offers.values(),
            key=lambda o: o.price / o.energy))
        )

        already_selected_bids = set()
        for offer in sorted_offers:
            for bid in sorted_bids:
                if bid.id not in already_selected_bids and \
                   offer.price / offer.energy <= bid.price / bid.energy and \
                   offer.seller != bid.buyer:
                    already_selected_bids.add(bid.id)
                    yield bid, offer
                    break

    def _delete_forwarded_bid_entries(self, bid):
        bid_info = self.forwarded_bids.pop(bid.id, None)
        if not bid_info:
            return
        self.forwarded_bids.pop(bid_info.target_bid.id, None)
        self.forwarded_bids.pop(bid_info.source_bid.id, None)

    def _match_offers_bids(self):
        for bid, offer in self._perform_pay_as_bid_matching():
            selected_energy = bid.energy if bid.energy < offer.energy else offer.energy
            original_bid_rate = bid.original_bid_price / bid.energy
            clearing_rate = bid.price / bid.energy

            self.owner.accept_offer(market=self.markets.source,
                                    offer=offer,
                                    buyer=bid.buyer,
                                    energy=selected_energy,
                                    trade_rate=clearing_rate,
                                    already_tracked=False,
                                    original_trade_rate=original_bid_rate)
            self._delete_forwarded_offer_entries(offer)
            self.markets.source.accept_bid(bid,
                                           selected_energy,
                                           seller=offer.seller,
                                           buyer=bid.buyer,
                                           already_tracked=True,
                                           trade_rate=clearing_rate,
                                           original_trade_rate=original_bid_rate)

            bid_info = self.forwarded_bids.get(bid.id, None)
            if bid_info is not None:
                self.delete_forwarded_bids(bid_info)

    def tick(self, *, area):
        super().tick(area=area)

        for bid_id, bid in self.markets.source.bids.items():
            if bid_id not in self.forwarded_bids and \
                    self.owner.usable_bid(bid) and \
                    self.owner.name != bid.buyer:
                self._forward_bid(bid)
        self._match_offers_bids()

    def delete_forwarded_bids(self, bid_info):
        try:
            self.markets.target.delete_bid(bid_info.target_bid)
        except BidNotFound:
            self.owner.log.debug(f"Bid {bid_info.target_bid.id} not "
                                 f"found in the target market.")
        self._delete_forwarded_bid_entries(bid_info.source_bid)

    def event_bid_traded(self, *, bid_trade):
        bid_info = self.forwarded_bids.get(bid_trade.offer.id)
        if not bid_info:
            return

        # Bid was traded in target market, buy in source
        if bid_trade.offer.id == bid_info.target_bid.id:
            market_bid = self.markets.source.bids[bid_info.source_bid.id]
            assert bid_trade.offer.energy <= market_bid.energy, \
                f"Traded bid on target market has more energy than the market bid."

            source_rate = bid_info.source_bid.price / bid_info.source_bid.energy
            target_rate = bid_info.target_bid.price / bid_info.target_bid.energy
            assert source_rate >= target_rate, \
                f"bid: source_rate ({source_rate}) is not lower than target_rate ({target_rate})"

            trade_rate = (bid_trade.offer.price/bid_trade.offer.energy)

            source_trade = self.markets.source.accept_bid(
                market_bid,
                energy=bid_trade.offer.energy,
                seller=self.owner.name,
                already_tracked=False,
                trade_rate=trade_rate,
                original_trade_rate=bid_trade.original_trade_rate
            )

            self.after_successful_trade_event(source_trade, bid_info)
        # Bid was traded in the source market by someone else
        elif bid_trade.offer.id == bid_info.source_bid.id:
            self.delete_forwarded_bids(bid_info)
        else:
            raise Exception(f"Invalid bid state for IAA {self.owner.name}: "
                            f"traded bid {bid_trade} was not in offered bids tuple {bid_info}")

    def after_successful_trade_event(self, source_trade, bid_info):
        if source_trade.residual:
            target_residual_bid = self.bid_trade_residual.pop(bid_info.target_bid.id)
            assert target_residual_bid.id != source_trade.residual.id, \
                f"Residual bid from the trade ({source_trade.residual}) is not the same as the" \
                f" residual bid from event_bid_changed ({target_residual_bid})."
            assert source_trade.residual.id not in self.forwarded_bids, \
                f"Residual bid has not been forwarded even though it was transmitted via " \
                f"event_bid_trade."
            res_bid_info = BidInfo(source_trade.residual, target_residual_bid)
            self.forwarded_bids[source_trade.residual.id] = res_bid_info
            self.forwarded_bids[target_residual_bid.id] = res_bid_info
        self._delete_forwarded_bid_entries(bid_info.source_bid)

    def event_bid_deleted(self, *, bid):
        bid_id = bid.id if isinstance(bid, Bid) else bid
        bid_info = self.forwarded_bids.get(bid_id)

        if not bid_info:
            # Deletion doesn't concern us
            return

        if bid_info.source_bid.id == bid_id:
            # Bid in source market of an bid we're already offering in the target market
            # was deleted - also delete in target market
            try:
                self.delete_forwarded_bids(bid_info)
            except MarketException:
                self.owner.log.exception("Error deleting InterAreaAgent offer")
        self._delete_forwarded_bid_entries(bid_info.source_bid)

    def event_bid_changed(self, *, market_id, existing_bid, new_bid):
        market = self.owner._get_market_from_market_id(market_id)
        if market is None:
            return

        if market == self.markets.target:
            # one of our forwarded bids was split, so save the residual bid for handling
            # the upcoming trade event
            assert existing_bid.id not in self.bid_trade_residual, \
                "Bid should only change once before each trade, there has been already " \
                "an event_bid_changed for the same bid ({existing_bid.id})."
            self.bid_trade_residual[existing_bid.id] = new_bid
        if market == self.markets.source and existing_bid.id in self.forwarded_bids:
            # a bid in the source market was split - forward the new residual bid
            if not self.owner.usable_bid(existing_bid) or \
                    self.owner.name == existing_bid.seller:
                return

            bid_info = self.forwarded_bids.get(existing_bid.id)
            forwarded = self._forward_bid(new_bid)
            self.owner.log.info("Bid %s changed to residual bid %s",
                                bid_info.target_bid,
                                forwarded)
