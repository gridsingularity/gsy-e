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
import math
from logging import getLogger
from collections import OrderedDict

from d3a.models.market.two_sided_pay_as_bid import TwoSidedPayAsBid
from d3a.models.market.market_structures import MarketClearingState, BidOfferMatch, TradeBidInfo
from d3a_interface.constants_limits import ConstSettings
from d3a.d3a_core.util import add_or_create_key

log = getLogger(__name__)


class TwoSidedPayAsClear(TwoSidedPayAsBid):

    def __init__(self, time_slot=None, area=None,
                 notification_listener=None, readonly=False):
        super().__init__(time_slot, area, notification_listener, readonly)
        self.state = MarketClearingState()
        self.sorted_bids = []
        self.mcp_update_point = \
            self.area.config.ticks_per_slot / \
            ConstSettings.GeneralSettings.MARKET_CLEARING_FREQUENCY_PER_SLOT

    def __repr__(self):  # pragma: no cover
        return "<TwoSidedPayAsClear{} bids: {} (E: {} kWh V:{}) " \
               "offers: {} (E: {} kWh V: {}) trades: {} (E: {} kWh, V: {})>"\
            .format(" {}".format(self.time_slot_str),
                    len(self.bids),
                    sum(b.energy for b in self.bids.values()),
                    sum(b.price for b in self.bids.values()),
                    len(self.offers),
                    sum(o.energy for o in self.offers.values()),
                    sum(o.price for o in self.offers.values()),
                    len(self.trades),
                    self.accumulated_trade_energy,
                    self.accumulated_trade_price
                    )

    def _discrete_point_curve(self, obj_list, round_functor):
        cumulative = {}
        for obj in obj_list:
            rate = round_functor(obj.price / obj.energy)
            cumulative = add_or_create_key(cumulative, rate, obj.energy)
        return cumulative

    def _smooth_discrete_point_curve(self, obj, limit, asc_order=True):
        if asc_order:
            for i in range(limit + 1):
                obj[i] = obj.get(i, 0) + obj.get(i - 1, 0)
        else:
            for i in range((limit), 0, -1):
                obj[i] = obj.get(i, 0) + obj.get(i + 1, 0)
        return obj

    def _get_clearing_point(self, max_rate):
        for i in range(1, max_rate + 1):
            if self.state.cumulative_offers[self.area.now][i] >= \
                    self.state.cumulative_bids[self.area.now][i]:
                return i, self.state.cumulative_bids[self.area.now][i]

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
        self.sorted_bids = self.sorting(self.bids, True)

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

            self.state.cumulative_offers[self.area.now] = \
                self._smooth_discrete_point_curve(cumulative_offers, max_rate)
            self.state.cumulative_bids[self.area.now] = \
                self._smooth_discrete_point_curve(cumulative_bids, max_rate, False)
            return self._get_clearing_point(max_rate)

    def match_offers_bids(self):
        if not (self.area.current_tick + 1) % int(self.mcp_update_point) == 0:
            return
        time = self.area.now
        clearing = self._perform_pay_as_clear_matching()

        if clearing is None:
            return

        clearing_rate, clearing_energy = clearing
        if clearing_energy > 0:
            log.info(f"Market Clearing Rate: {clearing_rate} "
                     f"||| Clearing Energy: {clearing_energy} "
                     f"||| Clearing Market {self.area.name}")
            self.state.clearing[time] = (clearing_rate, clearing_energy)

        matchings = self._create_bid_offer_matchings(
            clearing_energy, self.sorted_offers, self.sorted_bids
        )

        for i in range(len(matchings)):
            match = matchings[i]
            offer = match.offer
            bid = match.bid

            assert math.isclose(match.offer_energy, match.bid_energy)
            selected_energy = match.offer_energy
            original_bid_rate = bid.original_bid_price / bid.energy
            trade_bid_info = TradeBidInfo(
                original_bid_rate=original_bid_rate,
                propagated_bid_rate=bid.price / bid.energy,
                original_offer_rate=offer.original_offer_price / offer.energy,
                propagated_offer_rate=offer.price / offer.energy,
                trade_rate=original_bid_rate)
            trade = self.accept_offer(offer_or_id=offer,
                                      buyer=bid.buyer,
                                      energy=selected_energy,
                                      trade_rate=clearing_rate,
                                      already_tracked=False,
                                      trade_bid_info=trade_bid_info,
                                      buyer_origin=bid.buyer_origin)
            bid_trade = self.accept_bid(bid=bid,
                                        energy=selected_energy,
                                        seller=offer.seller,
                                        buyer=bid.buyer,
                                        already_tracked=True,
                                        trade_rate=clearing_rate,
                                        trade_offer_info=trade_bid_info,
                                        seller_origin=offer.seller_origin)

            if trade.residual is not None or bid_trade.residual is not None:
                matchings = self._replace_offers_bids_with_residual_in_matching_list(
                    matchings, i+1, trade, bid_trade
                )

    @classmethod
    def _create_bid_offer_matchings(cls, clearing_energy, offer_list, bid_list):
        bid_offer_matchings = []

        residual_offer_energy = {}
        for bid in bid_list:
            bid_energy = bid.energy
            while bid_energy > 0.0:
                offer = offer_list.pop(0)
                offer_energy = residual_offer_energy.get(offer.id, offer.energy)
                if offer_energy - bid_energy > 0.000001:
                    # Bid completely covered
                    residual_offer_energy[offer.id] = offer_energy - bid_energy
                    # Place the offer at the front of the offer list to cover following bids
                    offer_list.insert(0, offer)
                    # Save the matching to accept later
                    bid_offer_matchings.append(
                        BidOfferMatch(bid=bid, bid_energy=bid_energy,
                                      offer=offer, offer_energy=bid_energy)
                    )
                    clearing_energy -= bid_energy
                    # Set the bid energy to 0 to move forward to the next bid
                    bid_energy = 0
                else:
                    # Save the matching offer to accept later
                    bid_offer_matchings.append(
                        BidOfferMatch(bid=bid, bid_energy=offer_energy,
                                      offer=offer, offer_energy=offer_energy)
                    )
                    # Subtract the offer energy from the bid, in order to not be taken into account
                    # from following matchings
                    bid_energy -= offer_energy
                    residual_offer_energy.pop(offer.id, None)

                    clearing_energy -= offer_energy
                if clearing_energy <= 0:
                    return bid_offer_matchings

        return bid_offer_matchings

    @classmethod
    def _replace_offers_bids_with_residual_in_matching_list(
            cls, matchings, start_index, offer_trade, bid_trade
    ):
        for j in range(start_index, len(matchings)):
            match = matchings[j]
            if match.offer.id == offer_trade.offer.id:
                match = match._replace(offer=offer_trade.residual)
            if match.bid.id == bid_trade.offer.id:
                match = match._replace(bid=bid_trade.residual)
            matchings[j] = match
        return matchings
