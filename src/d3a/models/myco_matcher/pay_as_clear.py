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

from d3a.models.market.market_structures import MarketClearingState, BidOfferMatch, Clearing
from d3a_interface.constants_limits import ConstSettings
from d3a.d3a_core.util import add_or_create_key
from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a.models.myco_matcher.base_matcher import BaseMatcher


log = getLogger(__name__)


class PayAsClear(BaseMatcher):
    def __init__(self):
        self.state = MarketClearingState()
        self.sorted_bids = []

    def _discrete_point_curve(self, obj_list, round_functor):
        cumulative = {}
        for obj in obj_list:
            rate = round_functor(obj.energy_rate)
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
        for rate in range(1, max_rate + 1):
            if self.state.cumulative_offers[rate] >= \
                    self.state.cumulative_bids[rate]:
                if self.state.cumulative_bids[rate] == 0:
                    return rate-1, self.state.cumulative_offers[rate-1]
                else:
                    return rate, self.state.cumulative_bids[rate]

    def _accumulated_energy_per_rate(self, offer_bid):
        energy_sum = 0
        accumulated = OrderedDict()
        for o in offer_bid:
            energy_sum += o.energy
            accumulated[o.price / o.energy] = energy_sum
        return accumulated

    def _clearing_point_from_supply_demand_curve(self, bids, offers):
        clearing = []
        for b_rate, b_energy in bids.items():
            for o_rate, o_energy in offers.items():
                if o_rate <= (b_rate + FLOATING_POINT_TOLERANCE):
                    if o_energy >= b_energy:
                        clearing.append(Clearing(b_rate, b_energy))
        # if cumulative_supply is greater than cumulative_demand
        if len(clearing) > 0:
            return clearing[0].rate, clearing[0].energy
        else:
            for b_rate, b_energy in bids.items():
                for o_rate, o_energy in offers.items():
                    if o_rate <= (b_rate + FLOATING_POINT_TOLERANCE):
                        if o_energy < b_energy:
                            clearing.append(Clearing(b_rate, o_energy))
            if len(clearing) > 0:
                return clearing[-1].rate, clearing[-1].energy

    def get_clearing_point(self, bids, offers, current_time):
        self.sorted_bids = self.sort_by_energy_rate(bids, True)
        self.sorted_offers = self.sort_by_energy_rate(offers)
        clearing = None

        if len(self.sorted_bids) == 0 or len(self.sorted_offers) == 0:
            return

        if ConstSettings.IAASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM == 1:
            cumulative_bids = self._accumulated_energy_per_rate(self.sorted_bids)
            cumulative_offers = self._accumulated_energy_per_rate(self.sorted_offers)
            self.state.cumulative_bids = cumulative_bids
            self.state.cumulative_offers = cumulative_offers
            ascending_rate_bids = OrderedDict(reversed(list(cumulative_bids.items())))
            clearing = self._clearing_point_from_supply_demand_curve(
                ascending_rate_bids, cumulative_offers)
        elif ConstSettings.IAASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM == 2:
            cumulative_bids = self._discrete_point_curve(self.sorted_bids, math.floor)
            cumulative_offers = self._discrete_point_curve(self.sorted_offers, math.ceil)
            max_rate = self._populate_market_cumulative_offer_and_bid(cumulative_bids,
                                                                      cumulative_offers)
            clearing = self._get_clearing_point(max_rate)
        if clearing is not None:
            self.state.clearing[current_time] = clearing[0]
        return clearing

    def calculate_match_recommendation(self, bids, offers, current_time):
        clearing = self.get_clearing_point(bids, offers, current_time)
        if clearing is None:
            return []

        clearing_rate, clearing_energy = clearing
        if clearing_energy > 0:
            log.info(f"Market Clearing Rate: {clearing_rate} "
                     f"||| Clearing Energy: {clearing_energy} ")
        matchings = self._create_bid_offer_matchings(
            clearing, self.sorted_offers, self.sorted_bids
            )
        return matchings

    def _populate_market_cumulative_offer_and_bid(self, cumulative_bids, cumulative_offers):
        max_rate = max(
            math.ceil(self.sorted_offers[-1].energy_rate),
            math.floor(self.sorted_bids[0].energy_rate)
        )
        self.state.cumulative_offers = \
            self._smooth_discrete_point_curve(cumulative_offers, max_rate)
        self.state.cumulative_bids = \
            self._smooth_discrete_point_curve(cumulative_bids, max_rate, False)
        return max_rate

    def match_offers_bids(self):
        pass

    @classmethod
    def _create_bid_offer_matchings(cls, clearing, offer_list, bid_list):
        clearing_rate, clearing_energy = clearing
        # Return value, holds the bid-offer matches
        bid_offer_matchings = []
        # Keeps track of the residual energy from offers that have been matched once,
        # in order for their energy to be correctly tracked on following bids
        residual_offer_energy = {}
        for bid in bid_list:
            bid_energy = bid.energy
            while bid_energy > FLOATING_POINT_TOLERANCE:
                # Get the first offer from the list
                offer = offer_list.pop(0)
                # See if this offer has been matched with another bid beforehand.
                # If it has, fetch the offer energy from the residual dict
                # Otherwise, use offer energy as is.
                offer_energy = residual_offer_energy.get(offer.id, offer.energy)
                if offer_energy - bid_energy > FLOATING_POINT_TOLERANCE:
                    # Bid energy completely covered by offer energy
                    # Update the residual offer energy to take into account the matched offer
                    residual_offer_energy[offer.id] = offer_energy - bid_energy
                    # Place the offer at the front of the offer list to cover following bids
                    # since the offer still has some energy left
                    offer_list.insert(0, offer)
                    # Save the matching
                    bid_offer_matchings.append(
                        BidOfferMatch(bid=bid, bid_energy=bid_energy,
                                      offer=offer, offer_energy=bid_energy,
                                      trade_rate=clearing_rate)
                    )
                    # Update total clearing energy
                    clearing_energy -= bid_energy
                    # Set the bid energy to 0 to move forward to the next bid
                    bid_energy = 0
                else:
                    # Offer is exhausted by the bid. More offers are needed to cover the bid.
                    # Save the matching offer to accept later
                    bid_offer_matchings.append(
                        BidOfferMatch(bid=bid, bid_energy=offer_energy,
                                      offer=offer, offer_energy=offer_energy,
                                      trade_rate=clearing_rate)
                    )
                    # Subtract the offer energy from the bid, in order to not be taken into account
                    # from following matchings
                    bid_energy -= offer_energy
                    # Remove the offer from the residual offer dictionary
                    residual_offer_energy.pop(offer.id, None)
                    # Update total clearing energy
                    clearing_energy -= offer_energy
                if clearing_energy <= FLOATING_POINT_TOLERANCE:
                    # Clearing energy has been satisfied by existing matches. Return the matches
                    return bid_offer_matchings

        return bid_offer_matchings
