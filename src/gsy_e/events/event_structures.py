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
from enum import Enum


class OfferEvent(Enum):
    """Events emitted by the Offer."""
    DELETED = 1
    ACCEPTED = 2


class MarketEvent(Enum):
    """Events emitted by the market classes."""
    OFFER = 1
    OFFER_SPLIT = 4
    OFFER_DELETED = 2
    OFFER_TRADED = 3
    BID = 12
    BID_TRADED = 5
    BID_DELETED = 6
    BID_SPLIT = 7
    BALANCING_OFFER = 8
    BALANCING_OFFER_SPLIT = 9
    BALANCING_OFFER_DELETED = 10
    BALANCING_TRADE = 11


class AreaEvent(Enum):
    """Events emitted by the Area class."""
    TICK = 1
    MARKET_CYCLE = 2
    BALANCING_MARKET_CYCLE = 3
    ACTIVATE = 4
