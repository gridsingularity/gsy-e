import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from pendulum import DateTime

logger = logging.getLogger(__name__)


class MarketType(Enum):
    """Enumeration of available market types."""

    SPOT = 0
    FLEXIBILITY = 1
    SETTLEMENT = 2


@dataclass(frozen=True)
class MarketSlotInfo:
    """Timing parameters for a single market slot, as returned by the API."""

    market_id: str
    community_id: str
    opening_time: DateTime
    closing_time: DateTime
    delivery_start_time: DateTime
    delivery_end_time: DateTime
    market_type: MarketType = MarketType.SPOT


# pylint: disable=too-many-instance-attributes
@dataclass(frozen=True)
class EnergyTrade:
    """A matched energy trade as reported by the external market."""

    market_id: str
    offer_id: str
    bid_id: str
    price: float
    energy_kWh: float
    seller: str
    buyer: str
    residual_offer_id: Optional[str]
    residual_bid_id: Optional[str]
