from d3a.models.market.two_sided import TwoSidedMarket


class SettlementMarket(TwoSidedMarket):

    @property
    def _class_name(self):
        return "SettlementMarket"

    @property
    def _debug_log_market_type_identifier(self):
        return "[SETTLEMENT]"
