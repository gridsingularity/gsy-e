from enum import Enum


class AvailableMarketTypes(Enum):
    """Collection of available market types
    Needs to be in this module in order to circumvent circular imports
    """

    SPOT = 0
    BALANCING = 1
    SETTLEMENT = 2
    FUTURE = 3
    HOUR_FORWARD = 4
    WEEK_FORWARD = 5
    MONTH_FORWARD = 6
    YEAR_FORWARD = 7


PAST_MARKET_TYPE_FILE_SUFFIX_MAPPING = {
    AvailableMarketTypes.SPOT: "",
    AvailableMarketTypes.BALANCING: "-balancing",
    AvailableMarketTypes.SETTLEMENT: "-settlement",
    AvailableMarketTypes.FUTURE: "-future",
    AvailableMarketTypes.HOUR_FORWARD: "-hour-ahead",
    AvailableMarketTypes.WEEK_FORWARD: "-week-ahead",
    AvailableMarketTypes.MONTH_FORWARD: "-month-ahead",
    AvailableMarketTypes.YEAR_FORWARD: "-year-ahead",
}
