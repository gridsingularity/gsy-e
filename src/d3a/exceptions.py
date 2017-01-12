class D3AException(Exception):
    pass


class SimulationException(D3AException):
    pass


class MarketException(D3AException):
    pass


class MarketReadOnlyException(MarketException):
    pass


class OfferNotFoundException(MarketException):
    pass


class InvalidTrade(MarketException):
    pass


class InvalidOffer(MarketException):
    pass


class AreaException(D3AException):
    pass
