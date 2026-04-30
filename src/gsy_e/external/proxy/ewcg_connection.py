import json
import logging
import os
import threading
import uuid
from decimal import Decimal
from typing import Callable, Optional

import httpx
import pendulum
from pendulum import DateTime
from websockets.sync.client import connect as ws_connect

from gsy_e.external.proxy.dataclasses import MarketType, MarketSlotInfo, EnergyTrade

logger = logging.getLogger(__name__)


# DDHub Client Gateway base URL, WebSocket endpoint path (used by the listener),
# and HTTP endpoint path (used to publish messages).
_CG_GATEWAY_URL: str = "PLACEHOLDER_GATEWAY_URL"
_CG_WS_PATH: str = "/events"
_CG_HTTP_MESSAGES_PATH: str = "/messages"

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

_WEBSOCKET_RECV_TIMEOUT: float = 1.0


class EWClientGatewayConnection:
    """
    Connection class for interaction with an external market via the Energy Web Client Gateway.
    """

    def __init__(self, actor_id: str, actor_type: str) -> None:
        self._actor_id = actor_id
        self._actor_type = actor_type
        base_url = _CG_GATEWAY_URL.rstrip("/")
        self._ws_url = base_url + _CG_WS_PATH
        self._http_url = base_url + _CG_HTTP_MESSAGES_PATH
        self._stop_event: threading.Event = threading.Event()
        self._subscription_thread: Optional[threading.Thread] = None

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
            "createdBy": {
                "int:Actor": {"int:actorName": self._actor_id, "int:actorType": self._actor_type}
            },
            "int:marketId": market_id,
            "int:orderType": "Bid",
            "int:quantity": energy_kWh,
            "int:priceLimit": float(rate),
            "int:timeSlot": int(time_slot.timestamp()),
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
            "int:createdBy": {
                "int:Actor": {"int:actorName": self._actor_id, "int:actorType": self._actor_type}
            },
            "int:marketId": market_id,
            "int:orderType": "Offer",
            "int:quantity": energy_kWh,
            "int:priceLimit": float(rate),
            "int:timeSlot": int(time_slot.timestamp()),
        }
        order_id = self._send_order(payload)
        if order_id:
            logger.debug("Posted offer, clientGatewayMessageId=%s", order_id)
        return order_id

    def delete_bid(self, time_slot: DateTime, order_id: str) -> None:
        """Send a request to delete a bid to the Client Gateway."""
        payload = {
            "int:orderId": order_id,
            "int:orderType": "Bid",
            "int:timeSlot": int(time_slot.timestamp()),
        }
        self._send_order(payload)

    def delete_offer(self, time_slot: DateTime, order_id: str) -> None:
        """Send a request to delete an offer to the Client Gateway."""
        payload = {
            "int:orderId": order_id,
            "int:orderType": "Offer",
            "int:timeSlot": int(time_slot.timestamp()),
        }
        self._send_order(payload)

    def _auth_headers(self) -> dict:
        """Return the authentication headers, reading the API key from the environment."""
        api_key = os.environ.get(_CG_API_KEY_ENV_VAR)
        if not api_key:
            raise EnvironmentError(f"Environment variable {_CG_API_KEY_ENV_VAR} is not set.")
        return {"x-api-key": api_key}

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
            response = httpx.post(
                self._http_url,
                json=envelope,
                headers=self._auth_headers(),
            )
            response.raise_for_status()
            return response.json().get("clientGatewayMessageId")
        # pylint: disable=broad-exception-caught
        except Exception:
            logger.exception("Failed to send order via HTTP (%s)", self._http_url)
            return None

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
                        raw = ws.recv(timeout=_WEBSOCKET_RECV_TIMEOUT)
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
        # pylint: disable=broad-exception-caught
        except Exception:
            logger.exception("WebSocket listener failed (%s)", self._ws_url)

    @staticmethod
    def _parse_market_slot(data: dict) -> MarketSlotInfo:
        return MarketSlotInfo(
            market_id=data["int:marketId"],
            community_id=data["int:communityId"],
            opening_time=pendulum.parse(data["int:openingTime"]),
            closing_time=pendulum.parse(data["int:closingTime"]),
            delivery_start_time=pendulum.parse(data["int:deliveryStartTime"]),
            delivery_end_time=pendulum.parse(data["int:deliveryEndTime"]),
            market_type=MarketType(data["int:marketType"]),
        )

    @staticmethod
    def _parse_trade(data: dict) -> EnergyTrade:
        return EnergyTrade(
            offer_id=data["int:offerId"],
            market_id=data["int:marketId"],
            bid_id=data["int:bidId"],
            price=data["int:price"],
            energy_kWh=data["int:energyKWh"],
            seller=data["int:seller"],
            buyer=data["int:buyer"],
            residual_offer_id=data.get("int:residualOfferId"),
            residual_bid_id=data.get("int:residualBidId"),
        )
