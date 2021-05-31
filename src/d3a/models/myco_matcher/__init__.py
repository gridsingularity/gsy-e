from d3a.global_utils import check_is_exact_match_type
from d3a.models.myco_matcher.external_matcher import ExternalMatcher
from d3a_interface.constants_limits import ConstSettings

from d3a.constants import BidOfferMatchAlgoEnum
from d3a.models.myco_matcher.pay_as_bid import PayAsBidMatcher
from d3a.models.myco_matcher.pay_as_clear import PayAsClearMatcher
from d3a.d3a_core.exceptions import WrongMarketTypeException


class MycoMatcher:
    def __init__(self):
        if check_is_exact_match_type(BidOfferMatchAlgoEnum.PAY_AS_BID):
            self.match_algorithm = PayAsBidMatcher()
        elif check_is_exact_match_type(BidOfferMatchAlgoEnum.PAY_AS_CLEAR):
            self.match_algorithm = PayAsClearMatcher()
        elif check_is_exact_match_type(BidOfferMatchAlgoEnum.CUSTOM):
            self.match_algorithm = ExternalMatcher()
        else:
            raise WrongMarketTypeException(f'Wrong market type setting flag '
                                           f'{ConstSettings.IAASettings.MARKET_TYPE}')

    def calculate_recommendation(self, bids, offers, current_time):
        return self.match_algorithm.calculate_match_recommendation(
            bids, offers, current_time)
