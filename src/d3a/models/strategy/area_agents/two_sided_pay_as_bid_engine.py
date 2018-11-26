from collections import namedtuple
from d3a.models.strategy.area_agents.one_sided_engine import IAAEngine
from d3a.d3a_core.exceptions import BidNotFound, MarketException
from d3a.models.market.market_structures import Bid

BidInfo = namedtuple('BidInfo', ('source_bid', 'target_bid'))


class TwoSidedPayAsBidEngine(IAAEngine):
    def __init__(self, name: str, market_1, market_2, min_offer_age: int, transfer_fee_pct: int,
                 owner: "InterAreaAgent"):
        super().__init__(name, market_1, market_2, min_offer_age, transfer_fee_pct, owner)
        self.forwarded_bids = {}  # type: Dict[str, BidInfo]

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
            bid.price + (bid.price * (self.transfer_fee_pct / 100)),
            bid.energy,
            self.owner.name,
            self.markets.target.area.name
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
            offer.price = offer.energy * (bid.price / bid.energy)
            self.owner.accept_offer(market=self.markets.source,
                                    offer=offer,
                                    buyer=bid.buyer,
                                    energy=selected_energy,
                                    price_drop=True)
            self._delete_forwarded_offer_entries(offer)

            self.markets.source.accept_bid(bid,
                                           selected_energy,
                                           seller=bid.seller,
                                           buyer=bid.buyer,
                                           already_tracked=True,
                                           price_drop=True)

    def tick(self, *, area):
        super().tick(area=area)

        for bid_id, bid in self.markets.source.bids.items():
            if bid_id not in self.forwarded_bids and \
                    self.owner.usable_bid(bid) and \
                    self.owner.name != bid.buyer:
                self._forward_bid(bid)

        self._match_offers_bids()

    def event_bid_traded(self, *, bid_trade):
        bid_info = self.forwarded_bids.get(bid_trade.offer.id)
        if not bid_info:
            return

        # Bid was traded in target market, buy in source
        if bid_trade.offer.id == bid_info.target_bid.id:
            source_price = bid_info.source_bid.price
            if bid_trade.price_drop:
                # Use the rate of the trade bid for accepting the source bid too
                source_price = bid_trade.offer.price
                # Drop the rate of the trade bid according to IAA fee
                source_price = source_price / (1 + (self.transfer_fee_pct / 100))

            self.markets.source.accept_bid(
                bid_info.source_bid._replace(price=source_price, energy=bid_trade.offer.energy),
                energy=bid_trade.offer.energy,
                seller=self.owner.name,
                already_tracked=False
            )
            if not bid_trade.residual:
                self._delete_forwarded_bid_entries(bid_info.target_bid)

        # Bid was traded in the source market by someone else
        elif bid_trade.offer.id == bid_info.source_bid.id:
            if self.owner.name == bid_trade.seller:
                return
            # Delete target bid
            try:
                self.markets.target.delete_bid(bid_info.target_bid)
            except BidNotFound:
                pass
            self._delete_forwarded_bid_entries(bid_info.source_bid)
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
            # Bid in source market of an bid we're already offering in the target market
            # was deleted - also delete in target market
            try:
                self.markets.target.delete_bid(bid_info.target_bid.id)
                self._delete_forwarded_bid_entries(bid_info.target_bid)
            except BidNotFound:
                self.owner.log.debug(f"Bid {bid_info.target_bid.id} not "
                                     f"found in the target market.")
            except MarketException:
                self.owner.log.exception("Error deleting InterAreaAgent offer")
        self._delete_forwarded_bid_entries(bid_info.source_bid)
