from d3a.constants import BidOfferMatchAlgoEnum
from d3a_interface.constants_limits import ConstSettings


def check_is_exact_match_type(bid_offer_match_algo: BidOfferMatchAlgoEnum):
    """Compares the matching algorithm set in IAASettings with the passed bid_offer_match_algo
    Returns True if both are matched
    """
    return ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE == bid_offer_match_algo.value
