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

from abc import ABC, abstractmethod
from typing import Tuple
from decimal import Decimal

from gsy_framework.data_classes import TradeBidOfferInfo, Bid, Offer


class BaseClassGridFees(ABC):
    """Grid fees are fees added to orders and therefore trades that are cleared.

    The buyer of energy is responsible for paying all the grid fees.
    This abstract class holds the interfaces for grid fees manager classes.
    """

    def __init__(self, grid_fee_rate: float):
        self.grid_fee_rate = Decimal(grid_fee_rate)

    @abstractmethod
    def update_incoming_bid_with_fee(
        self, source_rate: Decimal, original_rate: Decimal
    ) -> Decimal:
        """Add fees for bid's rate when posting it into a market."""

    @abstractmethod
    def update_incoming_offer_with_fee(
        self, source_rate: Decimal, original_rate: Decimal
    ) -> Decimal:
        """Add fees for offer's rate when posting it into a market."""

    @abstractmethod
    def update_forwarded_bid_with_fee(
        self, source_rate: Decimal, original_rate: Decimal
    ) -> Decimal:
        """Add fees for bid's rate when it's forwarded by another market."""

    @abstractmethod
    def update_forwarded_offer_with_fee(
        self, source_rate: Decimal, original_rate: Decimal
    ) -> Decimal:
        """Add fees for offer's rate when it's forwarded by another market."""

    @abstractmethod
    def update_forwarded_bid_trade_original_info(
        self, trade_original_info: TradeBidOfferInfo, market_bid: Bid
    ) -> TradeBidOfferInfo:
        """
        When a forwarded bid gets matched in a target market, it will also get matched in
        the source market with adjustments to the TradeBidOfferInfo of this trade.
        This method deals with duplicating and updating the TradeBidOfferInfo values.
        Args:
            trade_original_info: TradeBidOfferInfo instance created in the target market
            market_bid: the source bid instance that was cleared in a target market.

        Returns: TradeBidOfferInfo
        """

    @abstractmethod
    def update_forwarded_offer_trade_original_info(
        self, trade_original_info: TradeBidOfferInfo, market_offer: Offer
    ) -> TradeBidOfferInfo:
        """
        When a forwarded offer gets matched in a target market, it will also get matched in
        the source market with adjustments to the TradeBidOfferInfo of this trade.
        This method deals with duplicating and updating the TradeBidOfferInfo values.
        Args:
            trade_original_info: TradeBidOfferInfo instance created in the target market
            market_offer: the source offer instance that was cleared in a target market.

        Returns: TradeBidOfferInfo
        """

    @abstractmethod
    def propagate_original_bid_info_on_offer_trade(self, trade_original_info):
        """Add fees to the cleared bid trade.

        The reason we recalculate fees on trade even when we initially have these fees
        on the orders when they got forwarded is that the clearing rate is not always
        the offer or bid rate, It might change depending on the algorithm.
        """

    @abstractmethod
    def propagate_original_offer_info_on_bid_trade(self, trade_original_info, ignore_fees=False):
        """Add fees to the cleared offer trade.

        The reason we recalculate fees on trade even when we initially have these fees
        on the orders when they got forwarded is that the clearing rate is not always
        the offer or bid rate, It might change depending on the algorithm.
        """

    @abstractmethod
    def calculate_trade_price_and_fees(
        self, trade_bid_info: TradeBidOfferInfo
    ) -> Tuple[float, float, float]:
        """Return (revenue, grid fees, trade_price).
        revenue    : The actual amount that the offer seller will get
        grid fees  : The amount of fees the current market will get
        trade_price: The price the seller has to pay (revenue to the seller + grid fees)
        """

    @staticmethod
    @abstractmethod
    def calculate_original_trade_rate_from_clearing_rate(
        original_bid_rate, propagated_bid_rate, clearing_rate
    ):
        """
        Used for 2-sided pay as clear and matching engine matcher.
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
