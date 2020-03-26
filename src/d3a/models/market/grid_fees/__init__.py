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
    def propagate_original_offer_info_on_bid_trade(self, trade_original_info):
        pass

    @abstractmethod
    def calculate_trade_price_and_fees(self, trade_bid_info):
        pass
