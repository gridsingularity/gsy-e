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
        if source_rate is not None:
            return source_rate
        return original_rate

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

    def update_forwarded_bid_trade_original_info(self, trade_original_info, market_bid):
        if not trade_original_info:
            return None
        trade_offer_info = TradeBidOfferInfo(
            original_bid_rate=market_bid.original_energy_rate,
            propagated_bid_rate=trade_original_info.propagated_bid_rate or market_bid.energy_rate,
            original_offer_rate=trade_original_info.original_offer_rate,
            propagated_offer_rate=trade_original_info.propagated_offer_rate,
            trade_rate=trade_original_info.trade_rate)
        return trade_offer_info

    def update_forwarded_offer_trade_original_info(self, trade_original_info, market_offer):
        if not trade_original_info:
            return None
        trade_bid_info = TradeBidOfferInfo(
            original_bid_rate=trade_original_info.original_bid_rate,
            propagated_bid_rate=trade_original_info.propagated_bid_rate,
            original_offer_rate=market_offer.original_energy_rate,
            propagated_offer_rate=market_offer.energy_rate,
            trade_rate=trade_original_info.trade_rate)
        return trade_bid_info

    def propagate_original_bid_info_on_offer_trade(self, trade_original_info):
        if trade_original_info is None or trade_original_info.propagated_bid_rate is None:
            return None
        bid_rate = trade_original_info.propagated_bid_rate - self.grid_fee_rate
        trade_bid_info = TradeBidOfferInfo(
            original_bid_rate=trade_original_info.original_bid_rate,
            propagated_bid_rate=bid_rate,
            original_offer_rate=None,
            propagated_offer_rate=None,
            trade_rate=trade_original_info.trade_rate)
        return trade_bid_info

    def propagate_original_offer_info_on_bid_trade(self, trade_original_info, ignore_fees=False):
        grid_fee_rate = self.grid_fee_rate if not ignore_fees else 0.0
        offer_rate = trade_original_info.propagated_offer_rate + grid_fee_rate
        trade_offer_info = TradeBidOfferInfo(
            original_bid_rate=None,
            propagated_bid_rate=None,
            original_offer_rate=trade_original_info.original_offer_rate,
            propagated_offer_rate=offer_rate,
            trade_rate=trade_original_info.trade_rate)
        return trade_offer_info

    def calculate_trade_price_and_fees(self, trade_bid_info):
        bid_rate = trade_bid_info.propagated_bid_rate
        return bid_rate - self.grid_fee_rate, self.grid_fee_rate, bid_rate
