"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
    """General simulation exception."""


class MarketException(GSyException):
    """Exception of the MarketBase classes."""


class MarketReadOnlyException(MarketException):
    """Market is read-only and a mutate operation is performed."""


class OfferNotFoundException(MarketException):
    """Offer does not exist in the market."""


class BidNotFoundException(MarketException):
    """Bid does not exist in the market."""


class InvalidTrade(MarketException):
    """Trade that occurred was invalid."""


class InvalidOffer(MarketException):
    """Invalid offer was posted."""


class InvalidBid(MarketException):
    """Invalid bid was posted."""


class AreaException(GSyException):
    """Error during the operation of the Area class."""


class InvalidBalancingTradeException(MarketException):
    """Balancing trade that occurred was invalid."""


class DeviceNotInRegistryError(MarketException):
    """Device name is not a part of the registry."""


class D3ARedisException(GSyException):
    """Redis connection reported an error."""


class WrongMarketTypeException(GSyException):
    """Operation cannot be performed on the selected market type."""


class InvalidBidOfferPairException(GSyException):
    """Invalid match of bid and offer."""


class MatchingEngineValidationException(GSyException):
    """Matching Engine recommendations did not pass the validation check."""


class LiveEventException(GSyException):
    """Exception type for live event errors."""


class NegativePriceOrdersException(MarketException):
    """Exception type for errors regarding negative order prices."""


class NegativeEnergyOrderException(MarketException):
    """Exception type for errors of negative energy value in orders."""


class NegativeEnergyTradeException(MarketException):
    """Exception type for errors of negative energy value in Trades."""
