# pylint: disable=broad-exception-caught
import json
import logging
import os
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Callable, Optional

import pendulum
from pendulum import DateTime
from websockets.sync.client import connect as ws_connect

logger = logging.getLogger(__name__)


# DDHub Client Gateway base URL and WebSocket endpoint path.
_CG_GATEWAY_URL: str = "PLACEHOLDER_GATEWAY_URL"
_CG_WS_PATH: str = "/events"

# WebSocket subprotocol required by the DDHub Client Gateway.
_CG_WS_SUBPROTOCOL: str = "ddhub-protocol"

# Placeholder channel / topic identifiers — replace with real values once the
# channels and topics have been defined in the Client Gateway.
_CG_FQCN: str = "PLACEHOLDER_CHANNEL_NAME"
_CG_TOPIC_VERSION: str = "1.0.0"
_CG_TOPIC_OWNER: str = "PLACEHOLDER_TOPIC_OWNER"

# Environment variable that must hold the API key for the Client Gateway.
_CG_API_KEY_ENV_VAR: str = "EW_CLIENT_GATEWAY_API_KEY"

_CG_ORDER_TOPIC_NAME: str = "PLACEHOLDER_ORDER_TOPIC_NAME"
_CG_MARKET_SLOT_TOPIC_NAME: str = "PLACEHOLDER_MARKET_SLOT_TOPIC_NAME"
_CG_TRADE_TOPIC_NAME: str = "PLACEHOLDER_TRADE_TOPIC_NAME"


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


class Connection(ABC):
    """Abstract interface for interaction with an external market via an API."""

    def __init__(self, created_by: str) -> None:
        self._created_by = created_by

    @abstractmethod
    def post_bid(
        self,
        market_id: str,
        time_slot: DateTime,
        energy_kWh: float,
        rate: Decimal,
    ) -> Optional[str]:
        """Place a bid and return the server-assigned order ID, or None on failure."""

    @abstractmethod
    def post_offer(
        self,
        market_id: str,
        time_slot: DateTime,
        energy_kWh: float,
        rate: Decimal,
    ) -> Optional[str]:
        """Place an offer and return the server-assigned order ID, or None on failure."""

    @abstractmethod
    def delete_bid(self, time_slot: DateTime, order_id: str) -> None:
        """Cancel an open bid."""

    @abstractmethod
    def delete_offer(self, time_slot: DateTime, order_id: str) -> None:
        """Cancel an open offer."""


class EWClientGatewayConnection(Connection):
    """
    Connection class for interaction with an external market via the Energy Web Client Gateway.
    """

    def __init__(self, created_by: str) -> None:
        super().__init__(created_by)
        self._ws_url = _CG_GATEWAY_URL.rstrip("/") + _CG_WS_PATH
        self._stop_event: threading.Event = threading.Event()
        self._subscription_thread: Optional[threading.Thread] = None

    def _auth_headers(self) -> dict:
        """Return the authentication headers, reading the API key from the environment."""
        api_key = os.environ.get(_CG_API_KEY_ENV_VAR)
        if not api_key:
            raise EnvironmentError(f"Environment variable {_CG_API_KEY_ENV_VAR} is not set.")
        return {"x-api-key": api_key}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_order(self, inner_payload: dict) -> Optional[str]:
        envelope = {
            "fqcn": _CG_FQCN,
            "topicName": _CG_ORDER_TOPIC_NAME,
            "topicVersion": _CG_TOPIC_VERSION,
            "topicOwner": _CG_TOPIC_OWNER,
            "transactionId": str(uuid.uuid4()),
            "payload": json.dumps(inner_payload),
            "anonymousRecipient": [],
        }
        try:
            with ws_connect(
                self._ws_url,
                subprotocols=[_CG_WS_SUBPROTOCOL],
                additional_headers=self._auth_headers(),
            ) as ws:
                ws.send(json.dumps(envelope))
                raw = ws.recv()
            return json.loads(raw).get("clientGatewayMessageId")
        except Exception:
            logger.exception("Failed to send order via WebSocket (%s)", self._ws_url)
            return None

    def subscribe(
        self,
        on_market_slot: Callable[[MarketSlotInfo], None] = None,
        on_trade: Callable[[EnergyTrade], None] = None,
    ) -> None:
        """
        Start a background thread that maintains a persistent WebSocket connection and dispatches
        incoming messages to the appropriate callback based on the topic name.
        The connection stays open until stop_subscription is called. Only one subscription can be
        active at a time; calling this method while a subscription is already running is a no-op.
        """
        if self._subscription_thread and self._subscription_thread.is_alive():
            logger.warning("Subscription is already running.")
            return
        self._stop_event.clear()
        self._subscription_thread = threading.Thread(
            target=self._listener,
            args=(on_market_slot, on_trade),
            daemon=True,
            name="ewcg-ws-listener",
        )
        self._subscription_thread.start()

    def stop_subscription(self) -> None:
        """Signal the background subscription thread to stop and wait for it to exit."""
        self._stop_event.set()
        if self._subscription_thread:
            self._subscription_thread.join()
            self._subscription_thread = None

    def _listener(
        self,
        on_market_slot: Callable[[MarketSlotInfo], None],
        on_trade: Callable[[EnergyTrade], None],
    ) -> None:
        """
        Background thread body: receive envelopes and dispatch to the correct handler.
        Format of the incoming messages:
        {
          "fqcn": "test.pub.chnl",
          "topicName": "test_topic",
          "topicVersion": "1.0.1",
          "topicOwner": "ddhub.test",
          "transactionId": "45d5a89f-7c2c-48b0-ae9a-54f4128e818",
          "payload": "<custom-payload>"
        }
        """
        try:
            with ws_connect(
                self._ws_url,
                subprotocols=[_CG_WS_SUBPROTOCOL],
                additional_headers=self._auth_headers(),
            ) as ws:
                while not self._stop_event.is_set():
                    try:
                        raw = ws.recv(timeout=1.0)
                    except TimeoutError:
                        continue
                    try:
                        envelope = json.loads(raw)
                        topic = envelope.get("topicName")
                        # Payload is always sent as string, needs a second deserialization
                        payload = json.loads(envelope["payload"])
                        if topic == _CG_MARKET_SLOT_TOPIC_NAME and on_market_slot:
                            on_market_slot(self._parse_market_slot(payload))
                        elif topic == _CG_TRADE_TOPIC_NAME and on_trade:
                            on_trade(self._parse_trade(payload))
                        else:
                            logger.debug("Ignored message with topicName=%r", topic)
                    except (KeyError, ValueError):
                        logger.exception("Received malformed message: %s", raw)
        except Exception:
            logger.exception("WebSocket listener failed (%s)", self._ws_url)

    @staticmethod
    def _parse_market_slot(data: dict) -> MarketSlotInfo:
        return MarketSlotInfo(
            market_id=data["market_id"],
            community_id=data["community_id"],
            opening_time=pendulum.parse(data["opening_time"]),
            closing_time=pendulum.parse(data["closing_time"]),
            delivery_start_time=pendulum.parse(data["delivery_start_time"]),
            delivery_end_time=pendulum.parse(data["delivery_end_time"]),
            market_type=MarketType(data["market_type"]),
        )

    @staticmethod
    def _parse_trade(data: dict) -> EnergyTrade:
        return EnergyTrade(
            offer_id=data["offerId"],
            market_id=data["marketId"],
            bid_id=data["bidId"],
            price=data["price"],
            energy_kWh=data["energy_kWh"],
            seller=data["seller"],
            buyer=data["buyer"],
            residual_offer_id=data.get("residualOfferId"),
            residual_bid_id=data.get("residualBidId"),
        )

    def post_bid(
        self,
        market_id: str,
        time_slot: DateTime,
        energy_kWh: float,
        rate: Decimal,
    ) -> Optional[str]:
        """
        Publish a bid to the Client Gateway. Returns the clientGatewayMessageId as the order ID,
        or None on failure.
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
        Publish an offer to the Client Gateway. Returns the ``clientGatewayMessageId`` as the
        order ID, or ``None`` on failure.
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

    def delete_bid(self, time_slot: DateTime, order_id: str) -> None:
        """Send a request to delete a bid to the Client Gateway."""
        payload = {
            "orderId": order_id,
            "orderType": "Bid",
            "timeSlot": int(time_slot.timestamp()),
        }
        self._send_order(payload)

    def delete_offer(self, time_slot: DateTime, order_id: str) -> None:
        """Send a request to delete an offer to the Client Gateway."""
        payload = {
            "orderId": order_id,
            "orderType": "Offer",
            "timeSlot": int(time_slot.timestamp()),
        }
        self._send_order(payload)


class StubConnection(Connection):
    """
    Placeholder implementation that raises an Exception for every call. Use during development or
    in unit tests (via `unittest.mock.MagicMock`).
    """

    def post_bid(
        self, market_id: str, time_slot: DateTime, energy_kWh: float, rate: Decimal
    ) -> Optional[str]:
        raise NotImplementedError("post_bid is not yet implemented")

    def post_offer(
        self, market_id: str, time_slot: DateTime, energy_kWh: float, rate: Decimal
    ) -> Optional[str]:
        raise NotImplementedError("post_offer is not yet implemented")

    def delete_bid(self, time_slot: DateTime, order_id: str) -> None:
        raise NotImplementedError("delete_bid is not yet implemented")

    def delete_offer(self, time_slot: DateTime, order_id: str) -> None:
        raise NotImplementedError("delete_offer is not yet implemented")
