from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional

import requests
from pendulum import DateTime
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

# DDHub Client Gateway message endpoint path (relative to gateway_url).
_CG_MESSAGES_PATH: str = "/api/v2/messages"

# Placeholder channel / topic identifiers — replace with real values once the
# channel and topic have been defined in the Client Gateway.
_CG_FQCN: str = "PLACEHOLDER_CHANNEL_NAME"
_CG_TOPIC_NAME: str = "PLACEHOLDER_TOPIC_NAME"
_CG_TOPIC_VERSION: str = "1.0.0"
_CG_TOPIC_OWNER: str = "PLACEHOLDER_TOPIC_OWNER"


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
    Abstract interface for interaction with the external market via the Energy
    Web DDHub Client Gateway.

    Subclass this and implement each method once the real API endpoints and
    channel / topic names are known.  The docstrings on each method describe
    the expected message shape.

    Parameters
    ----------
    created_by:
        The identity of the trader (buyer name for bids, seller name for
        offers) sent in every order payload as the ``createdBy`` field.
    """

    def __init__(self, created_by: str) -> None:
        self._created_by = created_by

    @abstractmethod
    def get_active_market_slots(self) -> List[EWDSMarketSlotInfo]:
        """
        Return timing information for all currently active market slots.

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

        Inner payload published to the Client Gateway::

            {
              "createdBy":  "<buyer>",
              "marketId":   "<uuid>",
              "orderType":  "Bid",
              "quantity":   <float>,
              "priceLimit": <float>,
              "timeSlot":   <unix-timestamp>
            }
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

        Inner payload published to the Client Gateway::

            {
              "createdBy":  "<seller>",
              "marketId":   "<uuid>",
              "orderType":  "Offer",
              "quantity":   <float>,
              "priceLimit": <float>,
              "timeSlot":   <unix-timestamp>
            }
        """

    @abstractmethod
    def delete_bid(self, slot: DateTime, order_id: str) -> None:
        """Cancel an open bid."""

    @abstractmethod
    def delete_offer(self, slot: DateTime, order_id: str) -> None:
        """Cancel an open offer."""


class ClientGatewayEWDSConnection(EWDSConnection):
    """
    Concrete :class:`EWDSConnection` that submits orders to the Energy Web
    DDHub Client Gateway via its REST messaging API.

    Orders are posted as JSON payloads to ``POST /api/v2/messages``.  The
    Client Gateway routes each message internally to the configured channel and
    topic.  The ``clientGatewayMessageId`` returned in the response is used as
    the order ID.

    Receiving trade events (confirmations, cancellations, etc.) is handled
    separately via the Client Gateway's WebSocket endpoint
    (``ws://<host>/events``) which pushes messages to subscribed clients
    without polling.  WebSocket subscription support will be added in a future
    iteration.

    Parameters
    ----------
    created_by:
        Identity of the trader sent in the ``createdBy`` field of every order.
    gateway_url:
        Base URL of the DDHub Client Gateway instance,
        e.g. ``http://localhost:3333``.
    username:
        Basic-auth username configured on the Client Gateway
        (``API_USERNAME`` env var on the gateway side).
    password:
        Basic-auth password (``API_PASSWORD`` on the gateway side).
    """

    def __init__(
        self,
        created_by: str,
        gateway_url: str,
        username: str,
        password: str,
    ) -> None:
        super().__init__(created_by)
        self._messages_url = gateway_url.rstrip("/") + _CG_MESSAGES_PATH
        self._auth = HTTPBasicAuth(username, password)
        self._session = requests.Session()
        self._session.auth = self._auth

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_order(self, inner_payload: dict) -> Optional[str]:
        """
        Wrap *inner_payload* in a DDHub Client Gateway message envelope and
        POST it to the messages endpoint.

        Returns the ``clientGatewayMessageId`` from the response, or ``None``
        if the request fails.
        """
        envelope = {
            "fqcn": _CG_FQCN,
            "topicName": _CG_TOPIC_NAME,
            "topicVersion": _CG_TOPIC_VERSION,
            "topicOwner": _CG_TOPIC_OWNER,
            "transactionId": str(uuid.uuid4()),
            "payload": json.dumps(inner_payload),
            "anonymousRecipient": [],
        }
        try:
            response = self._session.post(self._messages_url, json=envelope, timeout=10)
            response.raise_for_status()
            return response.json().get("clientGatewayMessageId")
        except requests.RequestException:
            logger.exception("Failed to POST order to Client Gateway (%s)", self._messages_url)
            return None

    # ------------------------------------------------------------------
    # EWDSConnection interface
    # ------------------------------------------------------------------

    def get_active_market_slots(self) -> List[EWDSMarketSlotInfo]:
        # TODO: implement once active-slot retrieval is defined
        raise NotImplementedError("get_active_market_slots is not yet implemented")

    def post_bid(
        self,
        market_id: str,
        time_slot: DateTime,
        energy_kWh: float,
        rate: Decimal,
    ) -> Optional[str]:
        """
        Publish a bid to the Client Gateway.

        Returns the ``clientGatewayMessageId`` as the order ID, or ``None`` on
        failure.
        """
        payload = {
            "createdBy": self._created_by,
            "marketId": market_id,
            "orderType": "Bid",
            "quantity": energy_kWh,
            "priceLimit": float(rate),
            "timeSlot": int(time_slot.timestamp()),
        }
        order_id = self._send_order(payload)
        if order_id:
            logger.debug("Posted bid, clientGatewayMessageId=%s", order_id)
        return order_id

    def post_offer(
        self,
        market_id: str,
        time_slot: DateTime,
        energy_kWh: float,
        rate: Decimal,
    ) -> Optional[str]:
        """
        Publish an offer to the Client Gateway.

        Returns the ``clientGatewayMessageId`` as the order ID, or ``None`` on
        failure.
        """
        payload = {
            "createdBy": self._created_by,
            "marketId": market_id,
            "orderType": "Offer",
            "quantity": energy_kWh,
            "priceLimit": float(rate),
            "timeSlot": int(time_slot.timestamp()),
        }
        order_id = self._send_order(payload)
        if order_id:
            logger.debug("Posted offer, clientGatewayMessageId=%s", order_id)
        return order_id

    def delete_bid(self, slot: DateTime, order_id: str) -> None:
        # TODO: implement once the Client Gateway exposes a cancel-order endpoint
        raise NotImplementedError("delete_bid is not yet implemented")

    def delete_offer(self, slot: DateTime, order_id: str) -> None:
        # TODO: implement once the Client Gateway exposes a cancel-order endpoint
        raise NotImplementedError("delete_offer is not yet implemented")


class StubEWDSConnection(EWDSConnection):
    """
    Placeholder implementation — raises :class:`NotImplementedError` for every
    call.  Use during development or in unit tests (via
    :class:`unittest.mock.MagicMock`).
    """

    def __init__(self, created_by: str) -> None:
        super().__init__(created_by)

    def get_active_market_slots(self) -> List[EWDSMarketSlotInfo]:
        raise NotImplementedError("get_active_market_slots is not yet implemented")

    def post_bid(
        self, market_id: str, time_slot: DateTime, energy_kWh: float, rate: Decimal
    ) -> Optional[str]:
        raise NotImplementedError("post_bid is not yet implemented")

    def post_offer(
        self, market_id: str, time_slot: DateTime, energy_kWh: float, rate: Decimal
    ) -> Optional[str]:
        raise NotImplementedError("post_offer is not yet implemented")

    def delete_bid(self, slot: DateTime, order_id: str) -> None:
        raise NotImplementedError("delete_bid is not yet implemented")

    def delete_offer(self, slot: DateTime, order_id: str) -> None:
        raise NotImplementedError("delete_offer is not yet implemented")
