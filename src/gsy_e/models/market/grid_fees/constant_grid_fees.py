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
from gsy_e.models.market.grid_fees import BaseClassGridFees
from gsy_framework.data_classes import TradeBidOfferInfo


class ConstantGridFees(BaseClassGridFees):

    def update_incoming_bid_with_fee(self, source_bid, original_bid):
        if source_bid is None:
            return original_bid
        return source_bid

    def update_incoming_offer_with_fee(self, source_offer_price, original_price):
        if source_offer_price is None:
            return original_price + self.grid_fee_rate
        return source_offer_price + self.grid_fee_rate

    def calculate_original_trade_rate_from_clearing_rate(
            self, original_bid_rate, propagated_bid_rate,
            clearing_rate):
        """
        Used for 2-sided pay as clear and myco matcher.
        The purpose of this function is to adapt the
        clearing rate calculated via the clearing algorithm to match the expected price the
        original device has to pay once the trade chain settles. The clearing rate is scaled
        with regards to the demand side tax (to be precise, the ratio of the original bid rate to
        the propagated bid rate).
        :param original_bid_rate: Original bid rate
        :param propagated_bid_rate: Propagated bid rate
        :param clearing_rate: Clearing rate calculated by the matching algorithm
        :return: Original trade rate, that the original device has to pay once the trade
        chain settles.
        """
        return clearing_rate + (original_bid_rate - propagated_bid_rate)

    def update_forwarded_bid_with_fee(self, source_bid, original_bid):
        if source_bid is None:
            return original_bid - self.grid_fee_rate
        return source_bid - self.grid_fee_rate

    def update_forwarded_offer_with_fee(self, source_offer, original_offer):
        return source_offer

    def update_forwarded_bid_trade_original_info(self, trade_original_info, market_bid):
        if not trade_original_info:
            return None
        trade_offer_info = TradeBidOfferInfo(
            original_bid_rate=market_bid.original_price / market_bid.energy,
            propagated_bid_rate=market_bid.energy_rate,
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
            original_offer_rate=market_offer.original_price / market_offer.energy,
            propagated_offer_rate=market_offer.energy_rate,
            trade_rate=trade_original_info.trade_rate)
        return trade_bid_info

    def propagate_original_bid_info_on_offer_trade(self, trade_original_info):
        if trade_original_info is None:
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
