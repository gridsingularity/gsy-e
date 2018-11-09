from collections import namedtuple
from d3a.models.strategy.area_agents.two_sided_pay_as_bid_engine import TwoSidedPayAsBidEngine

BidInfo = namedtuple('BidInfo', ('source_bid', 'target_bid'))


class TwoSidedPayAsClearEngine(TwoSidedPayAsBidEngine):
    def __init__(self, name: str, market_1, market_2, min_offer_age: int, transfer_fee_pct: int,
                 owner: "InterAreaAgent"):
        super().__init__(name, market_1, market_2, min_offer_age, transfer_fee_pct, owner)
        self.forwarded_bids = {}  # type: Dict[str, BidInfo]

    def _perform_pay_as_clear_matching(self):

        # Sorted bids in descending order
        sorted_bids = list(reversed(sorted(self.markets.source.bids.values(),
                                           key=lambda b: b.price / b.energy)))

        # Sorted offers in descending order
        sorted_offers = list(sorted(self.markets.source.offers.values(),
                                    key=lambda o: o.price / o.energy))

        already_selected_bids = set()
        for offer in sorted_offers:
            for bid in sorted_bids:
                if bid.id not in already_selected_bids and \
                   offer.price / offer.energy <= bid.price / bid.energy and \
                   offer.seller != self.owner.name and \
                   offer.seller != bid.buyer:
                    already_selected_bids.add(bid.id)
                    yield bid, offer
                    break

    def _match_offers_bids(self):
        for bid, offer in self._perform_pay_as_bid_matching():
            selected_energy = bid.energy if bid.energy < offer.energy else offer.energy
            offer.price = offer.energy * (bid.price / bid.energy)
            self.owner.accept_offer(market=self.markets.source,
                                    offer=offer,
                                    buyer=self.owner.name,
                                    energy=selected_energy,
                                    price_drop=True)
            self._delete_forwarded_offer_entries(offer)

            self.markets.source.accept_bid(bid,
                                           selected_energy,
                                           seller=offer.seller,
                                           buyer=bid.buyer,
                                           already_tracked=True,
                                           price_drop=True)
            self._delete_forwarded_bid_entries(bid)
