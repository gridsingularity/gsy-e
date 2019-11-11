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
from d3a.models.market.market_structures import MarketClearingState
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a.d3a_core.util import add_or_create_key

log = getLogger(__name__)


class TwoSidedPayAsClear(TwoSidedPayAsBid):

    def __init__(self, time_slot=None, bc=None, notification_listener=None, readonly=False,
                 transfer_fees=None, name=None):
        super().__init__(time_slot, bc, notification_listener, readonly, transfer_fees, name)
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
            if self.state.cumulative_offers[self.now][i] >= \
                    self.state.cumulative_bids[self.now][i]:
                return i, self.state.cumulative_bids[self.now][i]

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
            math.ceil(self.sorted_offers[-1].price / self.sorted_offers[-1].energy),
            math.floor(self.sorted_bids[0].price / self.sorted_bids[0].energy)
        )
        self.state.cumulative_offers[self.now] = \
            self._smooth_discrete_point_curve(cumulative_offers, max_rate)
        self.state.cumulative_bids[self.now] = \
            self._smooth_discrete_point_curve(cumulative_bids, max_rate, False)
        return max_rate

    def match_offers_bids(self):
        if not (self.current_tick + 1) % int(self.mcp_update_point) == 0:
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

        accepted_bids = self._accept_cleared_bids(clearing_rate, clearing_energy)
        self._accept_cleared_offers(clearing_rate, clearing_energy, accepted_bids)

    def _accept_cleared_bids(self, clearing_rate, clearing_energy):
        cumulative_traded_bids = 0
        accepted_bids = []
        for bid in self.sorted_bids:
            original_bid_rate = bid.original_bid_price / bid.energy
            trade_offer_info = [
                original_bid_rate, bid.price/bid.energy,
                clearing_rate, clearing_rate, clearing_rate]

            if cumulative_traded_bids >= clearing_energy:
                break
            elif (bid.price / bid.energy) >= clearing_rate and \
                    (clearing_energy - cumulative_traded_bids) >= bid.energy:
                cumulative_traded_bids += bid.energy
                trade = self.accept_bid(
                    bid=bid,
                    energy=bid.energy,
                    seller=self.name,
                    already_tracked=True,
                    trade_rate=clearing_rate,
                    trade_offer_info=trade_offer_info
                )
            elif (bid.price / bid.energy) >= clearing_rate and \
                    (0 < (clearing_energy - cumulative_traded_bids) < bid.energy):
                trade = self.accept_bid(
                    bid=bid,
                    energy=(clearing_energy - cumulative_traded_bids),
                    seller=self.name,
                    already_tracked=True,
                    trade_rate=clearing_rate,
                    trade_offer_info=trade_offer_info
                )
                cumulative_traded_bids += (clearing_energy - cumulative_traded_bids)
            else:
                assert False, "An error occurred, this point should never be reached."
            accepted_bids.append(trade)
        return accepted_bids

    def _accept_cleared_offers(self, clearing_rate, clearing_energy, accepted_bids):
        cumulative_traded_offers = 0
        for offer in self.sorted_offers:
            if cumulative_traded_offers >= clearing_energy:
                break
            elif (math.floor(offer.price / offer.energy)) <= clearing_rate and \
                    (clearing_energy - cumulative_traded_offers) >= offer.energy:
                # TODO: Used the clearing_rate as the original_trade_rate for the offers, because
                # currently an aggregated market is used. If/once a peer-to-peer market is
                # implemented, we should use the original bid rate for calculating the fees
                # on the source offers, similar to the two sided pay as bid market.

                # energy == None means to use the bid energy instead of the remaining clearing
                # energy
                accepted_bids = self._exhaust_offer_for_selected_bids(
                    offer, accepted_bids, clearing_rate, None
                )
                cumulative_traded_offers += offer.energy
            elif (math.floor(offer.price / offer.energy)) <= clearing_rate and \
                    (clearing_energy - cumulative_traded_offers) < offer.energy:
                accepted_bids = self._exhaust_offer_for_selected_bids(
                    offer, accepted_bids, clearing_rate, clearing_energy - cumulative_traded_offers
                )
                cumulative_traded_offers += (clearing_energy - cumulative_traded_offers)

    def _exhaust_offer_for_selected_bids(self, offer, accepted_bids, clearing_rate, energy):
        while len(accepted_bids) > 0:
            trade = accepted_bids.pop(0)
            bid_energy = trade.offer.energy
            if energy is not None:
                if bid_energy > energy:
                    bid_energy = energy
                energy -= bid_energy
            else:
                energy = offer.energy

            already_tracked = trade.offer.buyer == offer.seller
            trade_bid_info = [
                clearing_rate, clearing_rate,
                offer.original_offer_price/offer.energy, offer.price/offer.energy,
                clearing_rate]

            if bid_energy == offer.energy:
                trade._replace(seller_origin=offer.seller_origin)
                self.accept_offer(offer_or_id=offer,
                                  buyer=trade.offer.buyer,
                                  energy=offer.energy,
                                  already_tracked=already_tracked,
                                  trade_rate=clearing_rate,
                                  trade_bid_info=trade_bid_info,
                                  buyer_origin=trade.buyer_origin)
                return accepted_bids
            elif bid_energy > offer.energy:
                trade._replace(seller_origin=offer.seller_origin)
                self.accept_offer(offer_or_id=offer,
                                  buyer=trade.offer.buyer,
                                  energy=offer.energy,
                                  already_tracked=already_tracked,
                                  trade_rate=clearing_rate,
                                  trade_bid_info=trade_bid_info,
                                  buyer_origin=trade.buyer_origin)
                updated_bid = trade.offer
                updated_bid._replace(energy=trade.offer.energy - offer.energy)
                trade._replace(offer=updated_bid)
                accepted_bids = [trade] + accepted_bids
                return accepted_bids
            elif bid_energy < offer.energy:
                trade._replace(seller_origin=offer.seller_origin)
                offer_trade = self.accept_offer(
                    offer_or_id=offer,
                    buyer=trade.offer.buyer,
                    energy=bid_energy,
                    already_tracked=already_tracked,
                    trade_rate=clearing_rate,
                    trade_bid_info=trade_bid_info,
                    buyer_origin=trade.buyer_origin)
                assert offer_trade.residual is not None
                offer = offer_trade.residual
            if energy <= FLOATING_POINT_TOLERANCE:
                return accepted_bids
        assert False, "Accepted bids were not enough to satisfy the offer, should never " \
                      "reach this point."
