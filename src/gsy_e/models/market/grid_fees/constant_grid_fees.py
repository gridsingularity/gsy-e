"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
from gsy_framework.data_classes import TradeBidOfferInfo

from gsy_e.models.market.grid_fees import BaseClassGridFees


class ConstantGridFees(BaseClassGridFees):
    """
    The constant grid fee is a market based fee, defined in €/kWh and added to each
    trade that is cleared.
    """

    def update_incoming_bid_with_fee(self, source_rate, original_rate):
        return source_rate or original_rate

    def update_incoming_offer_with_fee(self, source_rate, original_rate):
        if source_rate is None:
            return original_rate + self.grid_fee_rate
        return source_rate + self.grid_fee_rate

    @staticmethod
    def calculate_original_trade_rate_from_clearing_rate(
            original_bid_rate, propagated_bid_rate, clearing_rate):
        return clearing_rate + (original_bid_rate - propagated_bid_rate)

    def update_forwarded_bid_with_fee(self, source_rate, original_rate):
        if source_rate is None:
            return original_rate - self.grid_fee_rate
        return source_rate - self.grid_fee_rate

    def update_forwarded_offer_with_fee(self, source_rate, original_rate):
        return source_rate

    def adapt_bid_fees_on_bid_trade(self, trade_original_info, market_bid):
        if not trade_original_info:
            return None, None, None
        if trade_original_info.propagated_bid_rate:
            # When DoF is active, read the rate used in the trade market adding the current
            # market's grid fee
            propagated_bid_rate = trade_original_info.propagated_bid_rate + self.grid_fee_rate
        else:
            propagated_bid_rate = market_bid.energy_rate + self.grid_fee_rate
        return (
            trade_original_info.original_bid_rate, propagated_bid_rate,
            trade_original_info.trade_rate)

    def adapt_offer_fees_on_offer_trade(self, trade_original_info, market_offer):
        if not trade_original_info:
            return None, None, None
        original_offer_rate = market_offer.original_price / market_offer.energy
        return original_offer_rate, market_offer.energy_rate, trade_original_info.trade_rate

    def adapt_bid_fees_on_offer_trade(self, trade_original_info):
        if trade_original_info is None:
            return None, None, None
        bid_rate = trade_original_info.propagated_bid_rate - self.grid_fee_rate
        return trade_original_info.original_bid_rate, bid_rate, trade_original_info.trade_rate

    def adapt_offer_fees_on_bid_trade(self, trade_original_info, ignore_fees=False):
        grid_fee_rate = self.grid_fee_rate if not ignore_fees else 0.0
        offer_rate = trade_original_info.propagated_offer_rate + grid_fee_rate
        return trade_original_info.original_offer_rate, offer_rate, trade_original_info.trade_rate

    def calculate_trade_price_and_fees(self, trade_bid_info):
        bid_rate = trade_bid_info.propagated_bid_rate
        return bid_rate - self.grid_fee_rate, self.grid_fee_rate, bid_rate
