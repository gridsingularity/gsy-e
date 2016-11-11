class D3AException(Exception):
    pass


class MarketException(D3AException):
    pass


class MarketReadOnlyException(MarketException):
    pass


class BidNotFoundException(MarketException):
    pass


class InvalidBid(MarketException):
    pass
