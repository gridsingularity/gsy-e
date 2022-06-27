from enum import Enum


class AvailableMarketTypes(Enum):
    """Collection of available market types
    Needs to be in this module in order to circumvent circular imports
    """

    SPOT = 0
    BALANCING = 1
    SETTLEMENT = 2
    FUTURE = 3
    DAY_FORWARD = 4
    WEEK_FORWARD = 5
    MONTH_FORWARD = 6
    YEAR_FORWARD = 7


PAST_MARKET_TYPE_FILE_SUFFIX_MAPPING = {
    AvailableMarketTypes.SPOT: "",
    AvailableMarketTypes.BALANCING: "-balancing",
    AvailableMarketTypes.SETTLEMENT: "-settlement",
    AvailableMarketTypes.FUTURE: "-future",
    AvailableMarketTypes.DAY_FORWARD: "-day-forward",
    AvailableMarketTypes.WEEK_FORWARD: "-week-forward",
    AvailableMarketTypes.MONTH_FORWARD: "-month-forward",
    AvailableMarketTypes.YEAR_FORWARD: "-year-forward",
}

FORWARD_MARKET_TYPES = [AvailableMarketTypes.DAY_FORWARD,
                        AvailableMarketTypes.WEEK_FORWARD,
                        AvailableMarketTypes.MONTH_FORWARD,
                        AvailableMarketTypes.YEAR_FORWARD]
