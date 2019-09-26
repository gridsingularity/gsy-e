from abc import ABC, abstractmethod


class GridFees(ABC):

    @staticmethod
    @abstractmethod
    def update_incoming_bid_with_fee(source_bid, original_bid, tax_percentage=None):
        pass

    @staticmethod
    @abstractmethod
    def update_incoming_offer_with_fee(source_offer_price, original_offer_price, tax_percentage):
        pass

    @staticmethod
    @abstractmethod
    def update_forwarded_bid_with_fee(source_bid, original_bid, tax_percentage_n):
        pass

    @staticmethod
    @abstractmethod
    def update_forwarded_offer_with_fee(source_offer, original_offer, tax_percentage_n):
        pass

    @staticmethod
    @abstractmethod
    def update_forwarded_bid_trade_original_info(trade_original_info, market_bid):
        pass

    @staticmethod
    @abstractmethod
    def update_forwarded_offer_trade_original_info(trade_original_info, market_offer):
        pass

    @staticmethod
    @abstractmethod
    def propagate_original_bid_info_on_offer_trade(trade_original_info, tax_percentage):
        pass

    @staticmethod
    @abstractmethod
    def propagate_original_offer_info_on_bid_trade(trade_original_info, tax_percentage):
        pass

    @staticmethod
    @abstractmethod
    def calculate_trade_price_and_fees(trade_bid_info, tax_percentage):
        pass
