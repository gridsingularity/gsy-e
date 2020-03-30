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
from d3a.models.market.grid_fees import BaseClassGridFees
from d3a.models.market.market_structures import TradeBidInfo


class GridFees(BaseClassGridFees):

    def update_incoming_bid_with_fee(self, source_bid, original_bid):
        if source_bid is None:
            return original_bid
        return source_bid

    def update_incoming_offer_with_fee(self, source_offer_price, original_offer_price):
        if source_offer_price is None:
            return original_offer_price * (1 + self.grid_fee_rate)
        return source_offer_price + original_offer_price * self.grid_fee_rate

    def calculate_fee_revenue_from_clearing_trade(
            self, bid_propagated_rate, bid_original_rate,
            offer_propagated_rate, offer_original_rate,
            trade_rate_source
    ):
        demand_side_tax = 0 \
            if bid_original_rate == 0 \
            else 1 - bid_propagated_rate / bid_original_rate
        supply_side_tax = 0 \
            if offer_original_rate == 0 \
            else offer_propagated_rate / offer_original_rate - 1
        total_grid_fee_rate = demand_side_tax + supply_side_tax
        revenue = trade_rate_source / (1 + total_grid_fee_rate)
        grid_fee_rate = revenue * self.grid_fee_rate
        trade_price = revenue + revenue * supply_side_tax
        return revenue, grid_fee_rate, trade_price

    def calculate_original_trade_rate_from_clearing_rate(
            self, original_bid_rate, propagated_bid_rate,
            clearing_rate):
        """
        Used only for 2-sided pay as clear market. The purpose of this function is to adapt the
        clearing rate calculated via the clearing algorithm to match the expected price the
        original device has to pay once the trade chain settles. The clearing rate is scaled
        with regards to the demand side tax (to be precise, the ratio of the original bid rate to
        the propagated bid rate).
        :param original_bid_rate: Original bid rate
        :param propagated_bid_rate: Propagated bid rate
        :param clearing_rate: Clearing rate calculated by the 2-sided pay as clear algorithm
        :return: Original trade rate, that the original device has to pay once the trade
        chain settles.
        """
        return clearing_rate * (original_bid_rate / propagated_bid_rate)

    def update_forwarded_bid_with_fee(self, source_bid, original_bid):
        if source_bid is None:
            return original_bid * (1 - self.grid_fee_rate)
        return source_bid - original_bid * self.grid_fee_rate

    def update_forwarded_offer_with_fee(self, source_offer, original_offer):
        return source_offer

    def update_forwarded_bid_trade_original_info(self, trade_original_info, market_bid):
        if not trade_original_info:
            return None
        original_offer_rate, offer_rate, trade_rate_source = trade_original_info
        return [market_bid.original_bid_price / market_bid.energy,
                market_bid.energy_rate,
                original_offer_rate,
                offer_rate,
                trade_rate_source]

    def update_forwarded_offer_trade_original_info(self, trade_original_info, market_offer):
        if not trade_original_info:
            return None
        original_bid_rate, bid_rate, trade_rate_source = trade_original_info
        trade_bid_info = TradeBidInfo(
            original_bid_rate=original_bid_rate, propagated_bid_rate=bid_rate,
            original_offer_rate=market_offer.original_offer_price / market_offer.energy,
            propagated_offer_rate=market_offer.energy_rate,
            trade_rate=trade_rate_source)
        return trade_bid_info

    def propagate_original_bid_info_on_offer_trade(self, trade_original_info):
        if trade_original_info is None:
            return None
        original_bid_rate, bid_rate, _, _, trade_rate_source = trade_original_info
        bid_rate = bid_rate - original_bid_rate * self.grid_fee_rate
        return [original_bid_rate, bid_rate, trade_rate_source]

    def propagate_original_offer_info_on_bid_trade(self, trade_original_info, ignore_fees=False):
        _, _, original_offer_rate, offer_rate, trade_rate_source = trade_original_info
        grid_fee_rate = self.grid_fee_rate if not ignore_fees else 0.0
        offer_rate = offer_rate + original_offer_rate * grid_fee_rate
        return [original_offer_rate, offer_rate, trade_rate_source]

    def calculate_trade_price_and_fees(self, trade_bid_info):
        original_bid_rate, bid_rate, original_offer_rate, \
            offer_rate, trade_rate_source = trade_bid_info

        revenue, grid_fee_rate, trade_price = self.calculate_fee_revenue_from_clearing_trade(
            bid_propagated_rate=bid_rate, bid_original_rate=original_bid_rate,
            offer_propagated_rate=offer_rate, offer_original_rate=original_offer_rate,
            trade_rate_source=trade_rate_source
        )
        return revenue, grid_fee_rate, trade_price
