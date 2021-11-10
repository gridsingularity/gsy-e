"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from gsy_framework.exceptions import GSyException


class SimulationException(GSyException):
    pass


class MarketException(GSyException):
    pass


class MarketReadOnlyException(MarketException):
    pass


class OfferNotFoundException(MarketException):
    pass


class BidNotFoundException(MarketException):
    pass


class InvalidTrade(MarketException):
    pass


class InvalidOffer(MarketException):
    pass


class InvalidBid(MarketException):
    pass


class AreaException(GSyException):
    pass


class InvalidBalancingTradeException(MarketException):
    pass


class DeviceNotInRegistryError(MarketException):
    pass


class D3ARedisException(GSyException):
    pass


class WrongMarketTypeException(GSyException):
    pass


class InvalidBidOfferPairException(GSyException):
    pass


class MycoValidationException(GSyException):
    pass
