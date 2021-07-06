from d3a_interface.enums import BidOfferMatchAlgoEnum
from d3a_interface.constants_limits import ConstSettings
from d3a_interface.matching_algorithms import (
    PayAsBidMatchingAlgorithm, PayAsClearMatchingAlgorithm
)
from d3a.d3a_core.exceptions import WrongMarketTypeException
from d3a.d3a_core.util import is_external_matching_enabled
from d3a.models.myco_matcher.external_matcher import ExternalMatcher


class MycoMatcher:
    """Interface for market matching, set the matching algorithm and expose recommendations."""

    def __init__(self):
        self.match_algorithm = None

    def reconfigure(self):
        """Reconfigure the myco matcher properties at runtime."""
        self.match_algorithm = self.get_matcher_algorithm()

    def get_matches_recommendations(self, data):
        """Wrapper for matching algorithm's matches recommendations."""
        return self.match_algorithm.get_matches_recommendations(data)

    @staticmethod
    def get_matcher_algorithm():
        """Return a myco matcher instance based on the global BidOffer match type.

        :raises:
            WrongMarketTypeException
        """
        if (ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE ==
                BidOfferMatchAlgoEnum.PAY_AS_BID.value):
            return PayAsBidMatchingAlgorithm()
        if (ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE ==
                BidOfferMatchAlgoEnum.PAY_AS_CLEAR.value):
            return PayAsClearMatchingAlgorithm()
        if is_external_matching_enabled():
            return ExternalMatcher()
        raise WrongMarketTypeException("Wrong market type setting flag "
                                       f"{ConstSettings.IAASettings.MARKET_TYPE}")
