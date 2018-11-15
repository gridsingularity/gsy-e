from collections import namedtuple
from d3a.models.strategy.area_agents.two_sided_pay_as_bid_engine import TwoSidedPayAsBidEngine
import math

BidInfo = namedtuple('BidInfo', ('source_bid', 'target_bid'))


class TwoSidedPayAsClearEngine(TwoSidedPayAsBidEngine):
    def __init__(self, name: str, market_1, market_2, min_offer_age: int, transfer_fee_pct: int,
                 owner: "InterAreaAgent"):
        super().__init__(name, market_1, market_2, min_offer_age, transfer_fee_pct, owner)
        self.forwarded_bids = {}  # type: Dict[str, BidInfo]

    def _perform_pay_as_clear_matching(self):

        # Sorted bids in descending order
        sorted_bids = list(reversed(sorted(
            self.markets.source.bids.values(),
            key=lambda b: b.price / b.energy)))

        print(f"Sorted Bids: {sorted_bids}")

        # Sorted offers in ascending order
        sorted_offers = list(sorted(
            self.markets.source.offers.values(),
            key=lambda o: o.price / o.energy))

        print(f"Sorted Offers: {sorted_offers}")

        if len(sorted_bids) == 0 or len(sorted_offers) == 0:
            print(f"SKIP")
            return

        cumulative_bids = {}  # type: Dict[rate, cumulative_demand]
        cumulative_bids[math.floor(sorted_bids[0].price/sorted_bids[0].energy)] = \
            sorted_bids[0].energy
        for i in range(len(sorted_bids)):
            try:
                cumulative_bids[math.floor(sorted_bids[i+1].price / sorted_bids[i+1].energy)] += \
                    sorted_bids[0].energy
            except KeyError:
                cumulative_bids[math.floor(sorted_bids[i+1].price / sorted_bids[i+1].energy)] = \
                    sorted_bids[0].energy

        cumulative_offers = {}  # type: Dict[rate, cumulative_supply]
        cumulative_offers[math.floor(sorted_offers[0].price/sorted_offers[0].energy)] = \
            sorted_offers[0].energy

        for i in range(len(sorted_offers)):
            try:
                cumulative_offers[math.floor(sorted_offers[i+1].price /
                                             sorted_offers[i+1].energy)] += \
                    sorted_offers[0].energy
            except KeyError:
                cumulative_offers[math.floor(sorted_offers[i+1].price /
                                             sorted_offers[i+1].energy)] = \
                    sorted_offers[0].energy

        max_rate = int(max(math.floor(sorted_offers[-1].price / sorted_offers[-1].energy),
                       math.floor(sorted_bids[0].price / sorted_bids[0].energy)))

        for i in range(max_rate):
            try:
                supply = cumulative_offers[i]
                demand = cumulative_bids[i]
                if demand > supply:
                    continue
                else:
                    print(f"MCP: {i}")
                    return i
            except IndexError:
                continue

    def _match_offers_bids(self):
        self._perform_pay_as_clear_matching()
        # for bid, offer in self._perform_pay_as_bid_matching():
        #     selected_energy = bid.energy if bid.energy < offer.energy else offer.energy
        #     offer.price = offer.energy * (bid.price / bid.energy)
        #     self.owner.accept_offer(market=self.markets.source,
        #                             offer=offer,
        #                             buyer=self.owner.name,
        #                             energy=selected_energy,
        #                             price_drop=True)
        #     self._delete_forwarded_offer_entries(offer)
        #
        #     self.markets.source.accept_bid(bid,
        #                                    selected_energy,
        #                                    seller=offer.seller,
        #                                    buyer=bid.buyer,
        #                                    already_tracked=True,
        #                                    price_drop=True)
        #     self._delete_forwarded_bid_entries(bid)

    def tick(self, *, area):
        super().tick(area=area)

        for bid_id, bid in self.markets.source.bids.items():
            if bid_id not in self.forwarded_bids and \
                    self.owner.usable_bid(bid) and \
                    self.owner.name != bid.seller:
                self._forward_bid(bid)
        current_tick_number = area.current_tick % area.config.ticks_per_slot
        if current_tick_number % 500 == 0:
            print(f"_match_offers_bids")
            self._match_offers_bids()
