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
from collections import namedtuple, defaultdict
from d3a.models.strategy.area_agents.two_sided_pay_as_bid_engine import TwoSidedPayAsBidEngine
import math
from logging import getLogger
from d3a.models.const import ConstSettings

BidInfo = namedtuple('BidInfo', ('source_bid', 'target_bid'))

log = getLogger(__name__)


class TwoSidedPayAsClearEngine(TwoSidedPayAsBidEngine):
    def __init__(self, name: str, market_1, market_2, min_offer_age: int, transfer_fee_pct: int,
                 owner: "InterAreaAgent"):
        super().__init__(name, market_1, market_2, min_offer_age, transfer_fee_pct, owner)
        self.forwarded_bids = {}  # type: Dict[str, BidInfo]
        self.sorted_bids = []
        self.sorted_offers = []
        self.clearing_rate = []  # type: List[int]

    def __repr__(self):
        return "<TwoSidedPayAsClearEngine [{s.owner.name}] {s.name} " \
               "{s.markets.source.time_slot:%H:%M}>".format(s=self)

    def _sorting(self, obj, reverse_order=False):
        if reverse_order:
            # Sorted bids in descending order
            return list(reversed(sorted(
                obj.values(),
                key=lambda b: b.price / b.energy)))

        else:
            # Sorted bids in ascending order
            return list(sorted(
                obj.values(),
                key=lambda b: b.price / b.energy))

    def _discrete_point_curve(self, obj):
        cumulative = defaultdict(int)
        rate = math.floor(obj[0].price/obj[0].energy)
        cumulative[rate] = obj[0].energy
        for i in range(len(obj)):
            if len(obj) <= 1 or i == (len(obj) - 1):
                break
            rate = math.floor(obj[i+1].price / obj[i+1].energy)
            cumulative[rate] += obj[i].energy
        return cumulative

    def _smooth_discrete_point_curve(self, obj, limit, asc_order=True):
        if asc_order:
            for i in range(limit+1):
                obj[i] = obj.get(i, 0) + obj.get(i-1, 0)
        else:
            for i in range((limit), 0, -1):
                obj[i] = obj.get(i, 0) + obj.get(i+1, 0)
        return obj

    def _perform_pay_as_clear_matching(self):
        self.sorted_bids = self._sorting(self.markets.source.bids, True)
        self.sorted_offers = self._sorting(self.markets.source.offers)

        if len(self.sorted_bids) == 0 or len(self.sorted_offers) == 0:
            return

        cumulative_bids = self._discrete_point_curve(self.sorted_bids)
        cumulative_offers = self._discrete_point_curve(self.sorted_offers)

        max_rate = \
            int(max(math.floor(self.sorted_offers[-1].price / self.sorted_offers[-1].energy),
                    math.floor(self.sorted_bids[0].price / self.sorted_bids[0].energy)))

        cumulative_offers = self._smooth_discrete_point_curve(cumulative_offers, max_rate)
        cumulative_bids = self._smooth_discrete_point_curve(cumulative_bids, max_rate, False)

        for i in range(1, max_rate+1):
            if cumulative_offers[i] >= cumulative_bids[i]:
                return i, cumulative_bids[i]
            else:
                continue

    def _match_offers_bids(self):
        clearing = self._perform_pay_as_clear_matching()
        if clearing is None:
            return
        clearing_rate, clearing_energy = clearing
        if clearing_energy > 0:
            self.owner.log.info(f"Market Clearing Rate: {clearing_rate} "
                                f"||| Clearing Energy: {clearing_energy} ")
            self.clearing_rate.append(clearing_rate)

        cumulative_traded_bids = 0
        for bid in self.sorted_bids:
            already_tracked = self.owner.name == bid.buyer
            if cumulative_traded_bids >= clearing_energy:
                break
            elif (bid.price/bid.energy) >= clearing_rate and \
                    (clearing_energy - cumulative_traded_bids) >= bid.energy:
                cumulative_traded_bids += bid.energy
                self.markets.source.accept_bid(
                    bid._replace(price=(bid.energy * clearing_rate), energy=bid.energy),
                    energy=bid.energy,
                    seller=self.owner.name,
                    price_drop=True,
                    already_tracked=already_tracked
                )
            elif (bid.price/bid.energy) >= clearing_rate and \
                    (0 < (clearing_energy - cumulative_traded_bids) <= bid.energy):

                self.markets.source.accept_bid(
                    bid._replace(price=(bid.energy * clearing_rate), energy=bid.energy),
                    energy=(clearing_energy - cumulative_traded_bids),
                    seller=self.owner.name,
                    price_drop=True,
                    already_tracked=already_tracked
                )
                cumulative_traded_bids += (clearing_energy - cumulative_traded_bids)
            self._delete_forwarded_bid_entries(bid)

        cumulative_traded_offers = 0
        for offer in self.sorted_offers:
            already_tracked = self.owner.name == offer.seller
            if cumulative_traded_offers >= clearing_energy:
                break
            elif (math.floor(offer.price/offer.energy)) <= clearing_rate and \
                    (clearing_energy - cumulative_traded_offers) >= offer.energy:
                offer.price = offer.energy * clearing_rate
                self.owner.accept_offer(market=self.markets.source,
                                        offer=offer,
                                        buyer=self.owner.name,
                                        energy=offer.energy,
                                        price_drop=True,
                                        already_tracked=already_tracked)
                cumulative_traded_offers += offer.energy
            elif (math.floor(offer.price/offer.energy)) <= clearing_rate and \
                    (clearing_energy - cumulative_traded_offers) <= offer.energy:
                offer.price = offer.energy * clearing_rate
                self.owner.accept_offer(market=self.markets.source,
                                        offer=offer,
                                        buyer=self.owner.name,
                                        energy=clearing_energy - cumulative_traded_offers,
                                        price_drop=True,
                                        already_tracked=already_tracked)
                cumulative_traded_offers += (clearing_energy - cumulative_traded_offers)
            self._delete_forwarded_offer_entries(offer)

    def tick(self, *, area):
        super().tick(area=area)

        for bid_id, bid in self.markets.source.bids.items():
            if bid_id not in self.forwarded_bids and \
                    self.owner.usable_bid(bid) and \
                    self.owner.name != bid.seller:
                self._forward_bid(bid)
        current_tick_number = area.current_tick % area.config.ticks_per_slot
        self.mcp_update_point = \
            area.config.ticks_per_slot / \
            ConstSettings.GeneralSettings.MARKET_CLEARING_FREQUENCY_PER_SLOT
        if current_tick_number % int(self.mcp_update_point) == 0:
            self._match_offers_bids()
