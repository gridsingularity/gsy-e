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
from d3a.models.market.market_structures import MarketClearingState, BidOfferMatch, \
    TradeBidInfo, Clearing
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from d3a.d3a_core.util import add_or_create_key
from d3a.constants import FLOATING_POINT_TOLERANCE

log = getLogger(__name__)


class TwoSidedPayAsClear(TwoSidedPayAsBid):

    def __init__(self, time_slot=None, bc=None, notification_listener=None, readonly=False,
                 grid_fee_type=ConstSettings.IAASettings.GRID_FEE_TYPE,
                 transfer_fees=None, name=None, in_sim_duration=True):
        super().__init__(time_slot, bc, notification_listener, readonly,
                         grid_fee_type, transfer_fees, name,
                         in_sim_duration=in_sim_duration)
        self.state = MarketClearingState()
        self.sorted_bids = []
        self.mcp_update_point = \
            GlobalConfig.ticks_per_slot / \
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
            if self.state.cumulative_offers[self.now][rate] >= \
                    self.state.cumulative_bids[self.now][rate]:
                if self.state.cumulative_bids[self.now][rate] == 0:
                    return rate-1, self.state.cumulative_offers[self.now][rate-1]
                else:
                    return rate, self.state.cumulative_bids[self.now][rate]

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

    def _perform_pay_as_clear_matching(self):
        self.sorted_bids = self.sorting(self.bids, True)

        if len(self.sorted_bids) == 0 or len(self.sorted_offers) == 0:
            return

        if ConstSettings.IAASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM == 1:
            cumulative_bids = self._accumulated_energy_per_rate(self.sorted_bids)
            cumulative_offers = self._accumulated_energy_per_rate(self.sorted_offers)
            self.state.cumulative_bids[self.now] = cumulative_bids
            self.state.cumulative_offers[self.now] = cumulative_offers
            ascending_rate_bids = OrderedDict(reversed(list(cumulative_bids.items())))
            return self._clearing_point_from_supply_demand_curve(
                ascending_rate_bids, cumulative_offers)
        elif ConstSettings.IAASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM == 2:
            cumulative_bids = self._discrete_point_curve(self.sorted_bids, math.floor)
            cumulative_offers = self._discrete_point_curve(self.sorted_offers, math.ceil)
            max_rate = self._populate_market_cumulative_offer_and_bid(cumulative_bids,
                                                                      cumulative_offers)
            return self._get_clearing_point(max_rate)

    def _populate_market_cumulative_offer_and_bid(self, cumulative_bids, cumulative_offers):
        max_rate = max(
            math.ceil(self.sorted_offers[-1].energy_rate),
            math.floor(self.sorted_bids[0].energy_rate)
        )
        self.state.cumulative_offers[self.now] = \
            self._smooth_discrete_point_curve(cumulative_offers, max_rate)
        self.state.cumulative_bids[self.now] = \
            self._smooth_discrete_point_curve(cumulative_bids, max_rate, False)
        return max_rate

    def match_offers_bids(self):
        if not (self.current_tick_in_slot + 1) % int(self.mcp_update_point) == 0:
            return

        clearing = self._perform_pay_as_clear_matching()

        if clearing is None:
            return

        clearing_rate, clearing_energy = clearing
        if clearing_energy > 0:
            log.info(f"Market Clearing Rate: {clearing_rate} "
                     f"||| Clearing Energy: {clearing_energy} "
                     f"||| Clearing Market {self.name}")
            self.state.clearing[self.now] = (clearing_rate, clearing_energy)

        matchings = self._create_bid_offer_matchings(
            clearing_energy, self.sorted_offers, self.sorted_bids
        )

        for index, match in enumerate(matchings):
            offer = match.offer
            bid = match.bid

            assert math.isclose(match.offer_energy, match.bid_energy)

            selected_energy = match.offer_energy
            original_bid_rate = bid.original_bid_price / bid.energy
            propagated_bid_rate = bid.energy_rate
            offer_original_rate = offer.original_offer_price / offer.energy
            offer_propagated_rate = offer.energy_rate

            trade_rate_original = self.fee_class.calculate_original_trade_rate_from_clearing_rate(
                original_bid_rate, propagated_bid_rate, clearing_rate
            )

            trade_bid_info = TradeBidInfo(
                original_bid_rate=original_bid_rate,
                propagated_bid_rate=propagated_bid_rate,
                original_offer_rate=offer_original_rate,
                propagated_offer_rate=offer_propagated_rate,
                trade_rate=trade_rate_original)

            bid_trade, trade = self.accept_bid_offer_pair(
                bid, offer, clearing_rate, trade_bid_info, selected_energy
            )

            if trade.residual is not None or bid_trade.residual is not None:
                matchings = self._replace_offers_bids_with_residual_in_matching_list(
                    matchings, index+1, trade, bid_trade
                )

    @classmethod
    def _create_bid_offer_matchings(cls, clearing_energy, offer_list, bid_list):
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
                                      offer=offer, offer_energy=bid_energy)
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
                                      offer=offer, offer_energy=offer_energy)
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

    @classmethod
    def _replace_offers_bids_with_residual_in_matching_list(
            cls, matchings, start_index, offer_trade, bid_trade
    ):
        def _convert_match_to_residual(match):
            if match.offer.id == offer_trade.offer.id:
                assert offer_trade.residual is not None
                match = match._replace(offer=offer_trade.residual)
            if match.bid.id == bid_trade.offer.id:
                assert bid_trade.residual is not None
                match = match._replace(bid=bid_trade.residual)
            return match

        matchings[start_index:] = [_convert_match_to_residual(match)
                                   for match in matchings[start_index:]]
        return matchings
