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
from abc import ABC, abstractmethod


class BaseClassGridFees(ABC):

    def __init__(self, grid_fee_rate):
        self.grid_fee_rate = grid_fee_rate

    @abstractmethod
    def update_incoming_bid_with_fee(self, source_bid, original_bid):
        pass

    @abstractmethod
    def update_incoming_offer_with_fee(self, source_offer_price, original_offer_price):
        pass

    @abstractmethod
    def update_forwarded_bid_with_fee(self, source_bid, original_bid):
        pass

    @abstractmethod
    def update_forwarded_offer_with_fee(self, source_offer, original_offer):
        pass

    @abstractmethod
    def update_forwarded_bid_trade_original_info(self, trade_original_info, market_bid):
        pass

    @abstractmethod
    def update_forwarded_offer_trade_original_info(self, trade_original_info, market_offer):
        pass

    @abstractmethod
    def propagate_original_bid_info_on_offer_trade(self, trade_original_info):
        pass

    @abstractmethod
    def propagate_original_offer_info_on_bid_trade(self, trade_original_info, ignore_fees=False):
        pass

    @abstractmethod
    def calculate_trade_price_and_fees(self, trade_bid_info):
        pass
