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
from logging import getLogger

from d3a.models.market.two_sided_pay_as_bid import TwoSidedPayAsBid
from d3a.models.market.market_structures import TradeBidOfferInfo
from d3a_interface.constants_limits import ConstSettings

log = getLogger(__name__)

DEFAULT_PRECISION = 8
FLOATING_POINT_TOLERANCE = 0.00001


class BasicMarket(TwoSidedPayAsBid):

    def __init__(self, time_slot=None, bc=None, notification_listener=None, readonly=False,
                 grid_fee_type=ConstSettings.IAASettings.GRID_FEE_TYPE,
                 grid_fees=None, name=None, in_sim_duration=True):
        super().__init__(time_slot, bc, notification_listener, readonly, grid_fee_type,
                         grid_fees, name, in_sim_duration=in_sim_duration)

    def __repr__(self):  # pragma: no cover
        return "<BasicMarket{} bids: {} (E: {} kWh V:{}) " \
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

    def match_offers_bids(self):
        pass

    def match_recommendation(self, recommended_list):
        for bid, offer, matched_rate in recommended_list:
            selected_energy = bid.energy if bid.energy < offer.energy else offer.energy
            original_bid_rate = bid.original_bid_price / bid.energy
            if matched_rate > bid.energy_rate:
                continue

            trade_bid_info = TradeBidOfferInfo(
                original_bid_rate=original_bid_rate,
                propagated_bid_rate=bid.price/bid.energy,
                original_offer_rate=offer.original_offer_price/offer.energy,
                propagated_offer_rate=offer.price/offer.energy,
                trade_rate=original_bid_rate)

            self.accept_bid_offer_pair(bid, offer, matched_rate,
                                       trade_bid_info, selected_energy)
