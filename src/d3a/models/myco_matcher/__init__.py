from d3a.d3a_core.util import is_external_matching_enabled
from d3a.models.myco_matcher.external_matcher import ExternalMatcher
from d3a_interface.constants_limits import ConstSettings

from d3a.models.myco_matcher.pay_as_bid import PayAsBidMatcher
from d3a.models.myco_matcher.pay_as_clear import PayAsClearMatcher
from d3a.d3a_core.exceptions import WrongMarketTypeException
from d3a_interface.enums import BidOfferMatchAlgoEnum


class MycoMatcher:
    def __init__(self):
        self.match_algorithm = None

    def activate(self):
        """Method to be called upon the activation of MycoMatcher."""
        self.match_algorithm = self.get_matcher_algorithm()

    def calculate_recommendation(self, bids, offers, current_time):
        return self.match_algorithm.calculate_match_recommendation(
            bids, offers, current_time)

    @staticmethod
    def get_matcher_algorithm():
        """Return a myco matcher instance based on the global BidOffer match type.

        :raises:
            WrongMarketTypeException
        """
        if (ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE ==
                BidOfferMatchAlgoEnum.PAY_AS_BID.value):
            return PayAsBidMatcher()
        elif (ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE ==
                BidOfferMatchAlgoEnum.PAY_AS_CLEAR.value):
            return PayAsClearMatcher()
        elif is_external_matching_enabled():
            return ExternalMatcher()
        else:
            raise WrongMarketTypeException("Wrong market type setting flag "
                                           f"{ConstSettings.IAASettings.MARKET_TYPE}")
