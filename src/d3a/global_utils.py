from d3a.constants import BidOfferMatchAlgoEnum
from d3a_interface.constants_limits import ConstSettings


def is_custom_matching_enabled():
    """Checks if the bid offer match type is set to custom
    Returns True if both are matched
    """
    return (ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE ==
            BidOfferMatchAlgoEnum.CUSTOM.value)
