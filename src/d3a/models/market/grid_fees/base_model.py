from d3a.models.market.grid_fees import BaseClassGridFees


class GridFees(BaseClassGridFees):

    @staticmethod
    def update_incoming_bid_with_fee(source_bid, original_bid, tax_ratio=None):
        if source_bid is None:
            return original_bid
        return source_bid

    @staticmethod
    def update_incoming_offer_with_fee(source_offer_price, original_offer_price, tax_ratio):
        if source_offer_price is None:
            return original_offer_price * (1 + tax_ratio)
        return source_offer_price + original_offer_price * tax_ratio

    @staticmethod
    def calculate_fee_revenue_from_clearing_trade(
            bid_propagated_rate, bid_original_rate,
            offer_propagated_rate, offer_original_rate,
            trade_rate_source, tax_ratio
    ):
        demand_side_tax = 0 \
            if bid_original_rate == 0 \
            else 1 - bid_propagated_rate / bid_original_rate
        supply_side_tax = 0 \
            if offer_original_rate == 0 \
            else offer_propagated_rate / offer_original_rate - 1
        total_tax_ratio = demand_side_tax + supply_side_tax
        revenue = trade_rate_source / (1 + total_tax_ratio)
        fee_n = revenue * tax_ratio
        trade_price = revenue + revenue * supply_side_tax
        return revenue, fee_n, trade_price

    @staticmethod
    def update_forwarded_bid_with_fee(source_bid, original_bid, tax_ratio):
        if source_bid is None:
            return original_bid * (1 - tax_ratio)
        return source_bid - original_bid * tax_ratio

    @staticmethod
    def update_forwarded_offer_with_fee(source_offer, original_offer, tax_ratio):
        return source_offer

    @staticmethod
    def update_forwarded_bid_trade_original_info(trade_original_info, market_bid):
        if not trade_original_info:
            return None
        original_offer_rate, offer_rate, trade_rate_source = trade_original_info
        return [market_bid.original_bid_price / market_bid.energy,
                market_bid.price / market_bid.energy,
                original_offer_rate,
                offer_rate,
                trade_rate_source]

    @staticmethod
    def update_forwarded_offer_trade_original_info(trade_original_info, market_offer):
        if not trade_original_info:
            return None
        original_bid_rate, bid_rate, trade_rate_source = trade_original_info
        return [original_bid_rate,
                bid_rate,
                market_offer.original_offer_price / market_offer.energy,
                market_offer.price / market_offer.energy,
                trade_rate_source]

    @staticmethod
    def propagate_original_bid_info_on_offer_trade(trade_original_info, tax_ratio):
        if trade_original_info is None:
            return None
        original_bid_rate, bid_rate, _, _, trade_rate_source = trade_original_info
        bid_rate = bid_rate - original_bid_rate * tax_ratio
        return [original_bid_rate, bid_rate, trade_rate_source]

    @staticmethod
    def propagate_original_offer_info_on_bid_trade(trade_original_info, tax_ratio):
        _, _, original_offer_rate, offer_rate, trade_rate_source = trade_original_info
        offer_rate = offer_rate + original_offer_rate * tax_ratio
        return [original_offer_rate, offer_rate, trade_rate_source]

    @staticmethod
    def calculate_trade_price_and_fees(trade_bid_info, tax_ratio):
        original_bid_rate, bid_rate, original_offer_rate, \
            offer_rate, trade_rate_source = trade_bid_info

        revenue, fees, trade_price = GridFees.calculate_fee_revenue_from_clearing_trade(
            bid_rate, original_bid_rate,
            offer_rate, original_offer_rate,
            trade_rate_source, tax_ratio
        )
        return revenue, fees, trade_price
