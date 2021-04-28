from d3a_interface.constants_limits import ConstSettings

from d3a.constants import BID_OFFER_MATCH_TYPE
from d3a.constants import BidOfferMatchEnum
from d3a.models.myco_matcher.pay_as_bid import PayAsBidMatch
from d3a.models.myco_matcher.pay_as_clear import PayAsClear
from d3a.d3a_core.exceptions import WrongMarketTypeException


class MycoMatcher:
    def __init__(self):
        self.bid_offer_pairs = []
        if BID_OFFER_MATCH_TYPE == BidOfferMatchEnum.PAY_AS_BID.value:
            self.match_algorithm = PayAsBidMatch()
        elif BID_OFFER_MATCH_TYPE == BidOfferMatchEnum.PAY_AS_CLEAR.value:
            self.match_algorithm = PayAsClear()
        else:
            raise WrongMarketTypeException(f'Wrong market type setting flag '
                                           f'{ConstSettings.IAASettings.MARKET_TYPE}')

    def calculate_recommendation(self, bids, offers):
        self.bid_offer_pairs = []

        self.bid_offer_pairs = self.match_algorithm.calculate_match_recommendation(bids, offers)
