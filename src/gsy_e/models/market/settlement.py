from gsy_e.models.market.two_sided import TwoSidedMarket


class SettlementMarket(TwoSidedMarket):
    """
    Extends TwoSidedMarket class to support settlement markets. The behavior of these markets
    is exactly the same as the two sided market for now, only the bid/offer strategies change.
    """
    @property
    def _debug_log_market_type_identifier(self):
        return "[SETTLEMENT]"

    @staticmethod
    def type_name():
        """Return the market type representation."""
        return "Settlement Market"
