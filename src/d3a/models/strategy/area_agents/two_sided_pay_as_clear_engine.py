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
from d3a.models.const import ConstSettings
import math
from collections import OrderedDict
from logging import getLogger


BidInfo = namedtuple('BidInfo', ('source_bid', 'target_bid'))

log = getLogger(__name__)


class TwoSidedPayAsClearEngine(TwoSidedPayAsBidEngine):
    def __init__(self, name: str, market_1, market_2, min_offer_age: int,
                 owner: "InterAreaAgent"):
        super().__init__(name, market_1, market_2, min_offer_age, owner)
        self.forwarded_bids = {}  # type: Dict[str, BidInfo]
        self.sorted_bids = []
        self.sorted_offers = []

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

    def _discrete_point_curve(self, obj_list, round_functor):
        cumulative = defaultdict(int)
        for obj in obj_list:
            rate = round_functor(obj.price / obj.energy)
            cumulative[rate] += obj.energy
        return cumulative

    def _smooth_discrete_point_curve(self, obj, limit, asc_order=True):
        if asc_order:
            for i in range(limit+1):
                obj[i] = obj.get(i, 0) + obj.get(i-1, 0)
        else:
            for i in range((limit), 0, -1):
                obj[i] = obj.get(i, 0) + obj.get(i+1, 0)
        return obj

    def _get_clearing_point(self, max_rate):
        for i in range(1, max_rate+1):
            if self.markets.source.state.cumulative_offers[self.owner.owner.now][i] >= \
                    self.markets.source.state.cumulative_bids[self.owner.owner.now][i]:
                return i, self.markets.source.state.cumulative_bids[self.owner.owner.now][i]

    def _accumulated_energy_per_rate(self, offer_bid):
        energy_sum = 0
        accumulated = OrderedDict()
        for o in offer_bid:
            energy_sum += o.energy
            accumulated[o.price / o.energy] = energy_sum
        return accumulated

    def _clearing_point_from_supply_demand_curve(self, bids, offers):
        for b_rate, b_energy in bids.items():
            for o_rate, o_energy in offers.items():
                if o_rate <= b_rate and o_energy >= b_energy:
                    # Prone to change or be modularised once we add McAfee algorithm
                    return b_rate, b_energy

    def _perform_pay_as_clear_matching(self):
        self.sorted_bids = self._sorting(self.markets.source.bids, True)
        self.sorted_offers = self._sorting(self.markets.source.offers)

        if len(self.sorted_bids) == 0 or len(self.sorted_offers) == 0:
            return

        if ConstSettings.IAASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM == 1:
            cumulative_bids = self._accumulated_energy_per_rate(self.sorted_bids)
            cumulative_offers = self._accumulated_energy_per_rate(self.sorted_offers)
            ascending_rate_bids = OrderedDict(reversed(list(cumulative_bids.items())))
            return self._clearing_point_from_supply_demand_curve(
                ascending_rate_bids, cumulative_offers)
        elif ConstSettings.IAASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM == 2:
            cumulative_bids = self._discrete_point_curve(self.sorted_bids, math.floor)
            cumulative_offers = self._discrete_point_curve(self.sorted_offers, math.ceil)
            max_rate = max(
                math.floor(self.sorted_offers[-1].price / self.sorted_offers[-1].energy),
                math.floor(self.sorted_bids[0].price / self.sorted_bids[0].energy)
            )

            self.markets.source.state.cumulative_offers[self.owner.owner.now] = \
                self._smooth_discrete_point_curve(cumulative_offers, max_rate)
            self.markets.source.state.cumulative_bids[self.owner.owner.now] = \
                self._smooth_discrete_point_curve(cumulative_bids, max_rate, False)
            return self._get_clearing_point(max_rate)

    def _match_offers_bids(self):
        if not (self.owner.current_tick + 1) % int(self.owner.mcp_update_point) == 0:
            return
        time = self.owner.owner.now
        clearing = self._perform_pay_as_clear_matching()
        if clearing is None:
            return
        clearing_rate, clearing_energy = clearing
        if clearing_energy > 0:
            self.owner.log.info(f"Market Clearing Rate: {clearing_rate} "
                                f"||| Clearing Energy: {clearing_energy} ")
            self.markets.source.state.clearing[time] = (clearing_rate, clearing_energy)

        cumulative_traded_bids = 0
        for bid in self.sorted_bids:
            original_bid_rate = bid.original_bid_price / bid.energy
            if cumulative_traded_bids >= clearing_energy:
                break
            elif (bid.price/bid.energy) >= clearing_rate and \
                    (clearing_energy - cumulative_traded_bids) >= bid.energy:
                cumulative_traded_bids += bid.energy
                self.markets.source.accept_bid(
                    bid=bid,
                    energy=bid.energy,
                    seller=self.owner.name,
                    already_tracked=True,
                    trade_rate=clearing_rate,
                    original_trade_rate=original_bid_rate
                )
            elif (bid.price/bid.energy) >= clearing_rate and \
                    (0 < (clearing_energy - cumulative_traded_bids) <= bid.energy):

                self.markets.source.accept_bid(
                    bid=bid,
                    energy=(clearing_energy - cumulative_traded_bids),
                    seller=self.owner.name,
                    already_tracked=True,
                    trade_rate=clearing_rate,
                    original_trade_rate=original_bid_rate
                )
                cumulative_traded_bids += (clearing_energy - cumulative_traded_bids)
            self._delete_forwarded_bid_entries(bid)

        cumulative_traded_offers = 0
        for offer in self.sorted_offers:
            if cumulative_traded_offers >= clearing_energy:
                break
            elif (math.floor(offer.price/offer.energy)) <= clearing_rate and \
                    (clearing_energy - cumulative_traded_offers) >= offer.energy:
                # TODO: Used the clearing_rate as the original_trade_rate for the offers, because
                # currently an aggregated market is used. If/once a peer-to-peer market is
                # implemented, we should use the original bid rate for calculating the fees
                # on the source offers, similar to the two sided pay as bid market.
                self.owner.accept_offer(market=self.markets.source,
                                        offer=offer,
                                        buyer=self.owner.name,
                                        energy=offer.energy,
                                        already_tracked=False,
                                        trade_rate=clearing_rate,
                                        original_trade_rate=clearing_rate)
                cumulative_traded_offers += offer.energy
            elif (math.floor(offer.price/offer.energy)) <= clearing_rate and \
                    (clearing_energy - cumulative_traded_offers) <= offer.energy:
                self.owner.accept_offer(market=self.markets.source,
                                        offer=offer,
                                        buyer=self.owner.name,
                                        energy=clearing_energy - cumulative_traded_offers,
                                        already_tracked=False,
                                        trade_rate=clearing_rate,
                                        original_trade_rate=clearing_rate)
                cumulative_traded_offers += (clearing_energy - cumulative_traded_offers)

            self._delete_forwarded_offer_entries(offer)

    def tick(self, *, area):
        super().tick(area=area)
