from __future__ import annotations

from dataclasses import dataclass
import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional

from pendulum import DateTime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EWDSMarketSlotInfo:
    """Timing parameters for a single market slot, as returned by the HTTP API."""

    market_id: str
    opening_time: DateTime
    closing_time: DateTime
    delivery_start_time: DateTime
    delivery_end_time: DateTime


class EWDSConnection(ABC):
    """
    Abstract interface for HTTP interaction with the external market.

    Subclass this and implement each method once the real API endpoints are
    known.  The docstrings on each method describe the expected endpoint,
    request shape, and response shape.

    Parameters
    ----------
    created_by:
        The identity of the trader (buyer name for bids, seller name for
        offers) sent in every order request as the ``createdBy`` field.
    """

    def __init__(self, created_by: str) -> None:
        self._created_by = created_by

    @abstractmethod
    def get_active_market_slots(self) -> List[EWDSMarketSlotInfo]:
        """
        Return timing information for all currently active market slots.

        Stub endpoint: ``GET /markets/active``

        Expected response shape::

            [
              {
                "marketId":            "<uuid>",
                "opening_time":        "<ISO-8601>",
                "closing_time":        "<ISO-8601>",
                "delivery_start_time": "<ISO-8601>",
                "delivery_end_time":   "<ISO-8601>"
              },
              ...
            ]
        """

    @abstractmethod
    def post_bid(
        self,
        market_id: str,
        time_slot: DateTime,
        energy_kWh: float,
        rate: Decimal,
    ) -> Optional[str]:
        """
        Place a bid and return the server-assigned order ID, or ``None`` on
        failure.

        Stub endpoint: ``POST /orders``

        Request body::

            {
              "createdBy":  "<buyer>",
              "marketId":   "<uuid>",
              "orderType":  "Bid",
              "quantity":   <float>,
              "priceLimit": <float>,
              "timeSlot":   <unix-timestamp>
            }

        Response body::

            {"order_id": "<uuid>"}
        """

    @abstractmethod
    def post_offer(
        self,
        market_id: str,
        time_slot: DateTime,
        energy_kWh: float,
        rate: Decimal,
    ) -> Optional[str]:
        """
        Place an offer and return the server-assigned order ID, or ``None`` on
        failure.

        Stub endpoint: ``POST /orders``

        Request body::

            {
              "createdBy":  "<seller>",
              "marketId":   "<uuid>",
              "orderType":  "Offer",
              "quantity":   <float>,
              "priceLimit": <float>,
              "timeSlot":   <unix-timestamp>
            }

        Response body::

            {"order_id": "<uuid>"}
        """

    @abstractmethod
    def delete_bid(self, slot: DateTime, order_id: str) -> None:
        """
        Cancel an open bid.

        Stub endpoint: ``DELETE /orders/bids/<order_id>?time_slot=<ISO-8601>``
        """

    @abstractmethod
    def delete_offer(self, slot: DateTime, order_id: str) -> None:
        """
        Cancel an open offer.

        Stub endpoint: ``DELETE /orders/offers/<order_id>?time_slot=<ISO-8601>``
        """


class StubEWDSConnection(EWDSConnection):
    """
    Placeholder implementation — raises :class:`NotImplementedError` for every
    call.

    Replace each method body with a real HTTP call (e.g. using ``requests`` or
    ``httpx``) once the API endpoints are finalised.
    """

    def __init__(self, created_by: str) -> None:
        super().__init__(created_by)

    def get_active_market_slots(self) -> List[EWDSMarketSlotInfo]:
        # TODO: GET /markets/active
        raise NotImplementedError("get_active_market_slots is not yet implemented")

    def post_bid(
        self, market_id: str, time_slot: DateTime, energy_kWh: float, rate: Decimal
    ) -> Optional[str]:
        # TODO: POST /orders  (orderType: "Bid")
        raise NotImplementedError("post_bid is not yet implemented")

    def post_offer(
        self, market_id: str, time_slot: DateTime, energy_kWh: float, rate: Decimal
    ) -> Optional[str]:
        # TODO: POST /orders  (orderType: "Offer")
        raise NotImplementedError("post_offer is not yet implemented")

    def delete_bid(self, slot: DateTime, order_id: str) -> None:
        # TODO: DELETE /orders/bids/<order_id>
        raise NotImplementedError("delete_bid is not yet implemented")

    def delete_offer(self, slot: DateTime, order_id: str) -> None:
        # TODO: DELETE /orders/offers/<order_id>
        raise NotImplementedError("delete_offer is not yet implemented")
