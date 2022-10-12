from gsy_framework.enums import AvailableMarketTypes

PAST_MARKET_TYPE_FILE_SUFFIX_MAPPING = {
    AvailableMarketTypes.SPOT: "",
    AvailableMarketTypes.BALANCING: "-balancing",
    AvailableMarketTypes.SETTLEMENT: "-settlement",
    AvailableMarketTypes.FUTURE: "-future",
    AvailableMarketTypes.INTRADAY: "-intraday",
    AvailableMarketTypes.DAY_FORWARD: "-day-forward",
    AvailableMarketTypes.WEEK_FORWARD: "-week-forward",
    AvailableMarketTypes.MONTH_FORWARD: "-month-forward",
    AvailableMarketTypes.YEAR_FORWARD: "-year-forward",
}

FORWARD_MARKET_TYPES = [AvailableMarketTypes.INTRADAY,
                        AvailableMarketTypes.DAY_FORWARD,
                        AvailableMarketTypes.WEEK_FORWARD,
                        AvailableMarketTypes.MONTH_FORWARD,
                        AvailableMarketTypes.YEAR_FORWARD]
