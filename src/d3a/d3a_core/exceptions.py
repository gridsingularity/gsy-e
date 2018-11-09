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


class BidNotFound(MarketException):
    pass


class InvalidTrade(MarketException):
    pass


class InvalidOffer(MarketException):
    pass


class InvalidBid(MarketException):
    pass


class AreaException(D3AException):
    pass


class InvalidBalancingTradeException(MarketException):
    pass


class DeviceNotInRegistryError(MarketException):
    pass
