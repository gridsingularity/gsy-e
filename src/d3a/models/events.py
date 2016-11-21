from enum import Enum


class MarketEvent(Enum):
    OFFER = 1
    OFFER_DELETED = 2
    TRADE = 3


class AreaEvent(Enum):
    TICK = 1
    MARKET_CYCLE = 2
    ACTIVATE = 3
