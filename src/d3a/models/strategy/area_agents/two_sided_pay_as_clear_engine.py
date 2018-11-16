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
            if len(sorted_bids) <= 1 or i == (len(sorted_bids) - 1):
                print(f"breaking")
                break
            if cumulative_bids.get([math.floor(sorted_bids[i+1].price / sorted_bids[i+1].energy)])\
                    is not None:
                cumulative_bids[math.floor(sorted_bids[i+1].price / sorted_bids[i+1].energy)] += \
                    sorted_bids[i].energy
            else:
                cumulative_bids[math.floor(sorted_bids[i+1].price / sorted_bids[i+1].energy)] = \
                    sorted_bids[i].energy

        cumulative_offers = {}  # type: Dict[rate, cumulative_supply]
        cumulative_offers[math.floor(sorted_offers[0].price/sorted_offers[0].energy)] = \
            sorted_offers[0].energy

        for i in range(len(sorted_offers)):
            if len(sorted_offers) <= 1 or i == (len(sorted_offers) - 1):
                print(f"breaking")
                break
            if cumulative_offers.\
                    get(math.floor(sorted_offers[i+1].price / sorted_offers[i+1].energy))\
                    is not None:
                cumulative_offers[math.floor(sorted_offers[i+1].price /
                                             sorted_offers[i+1].energy)] += \
                    sorted_offers[i].energy
                print(f"sorted_offers[{i}].energy: {sorted_offers[i].energy}")
            else:
                cumulative_offers[math.floor(sorted_offers[i+1].price /
                                             sorted_offers[i+1].energy)] = \
                    sorted_offers[i].energy

        max_rate = int(max(math.floor(sorted_offers[-1].price / sorted_offers[-1].energy),
                       math.floor(sorted_bids[0].price / sorted_bids[0].energy)))

        for i in range(max_rate+1):
            if cumulative_offers.get(i) is None:
                if i == 0:
                    cumulative_offers[i] = 0
                else:
                    cumulative_offers[i] = cumulative_offers[i-1]
            else:
                if i == 0:
                    pass
                else:
                    cumulative_offers[i] = cumulative_offers[i] + cumulative_offers[i-1]
            print(f"supply@{i}: {cumulative_offers.get(i)}")

        for i in range((max_rate), 0, -1):
            if cumulative_bids.get(i) is None:
                if i == max_rate:
                    cumulative_bids[i] = 0
                else:
                    cumulative_bids[i] = 0
            else:
                if i == max_rate:
                    pass
                else:
                    cumulative_bids[i] = cumulative_bids[i] + cumulative_bids[i+1]

            print(f"demand@{i}: {cumulative_bids.get(i)}")

        for i in range(1, max_rate+1):
            supply = cumulative_offers[i]
            demand = cumulative_bids[i]
            if supply > demand:
                print(f"MCP: {i}")
                return i
                # Also write an algorithm for
            else:
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
