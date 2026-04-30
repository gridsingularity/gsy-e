# pylint: disable=missing-function-docstring, protected-access, missing-class-docstring
import json
import threading
from decimal import Decimal
from unittest.mock import MagicMock, patch

import httpx
import pendulum
import pytest

from gsy_e.external.proxy.dataclasses import EnergyTrade, MarketSlotInfo, MarketType
from gsy_e.external.proxy.ewcg_connection import EWClientGatewayConnection


SLOT_OPEN = pendulum.datetime(2024, 1, 1, 12, 0, tz="UTC")
SLOT_CLOSE = SLOT_OPEN.add(minutes=15)
DELIVERY_START = SLOT_CLOSE
DELIVERY_END = DELIVERY_START.add(minutes=15)
MARKET_ID = "market-uuid-001"
COMMUNITY_ID = "community-uuid"

ORDER_TOPIC = "PLACEHOLDER_ORDER_TOPIC_NAME"
MARKET_SLOT_TOPIC = "PLACEHOLDER_MARKET_SLOT_TOPIC_NAME"
TRADE_TOPIC = "PLACEHOLDER_TRADE_TOPIC_NAME"


@pytest.fixture(autouse=True)
def _api_key_env(monkeypatch):
    monkeypatch.setenv("EW_CLIENT_GATEWAY_API_KEY", "test-api-key")


def _ws_factory(recv_value=None, recv_side_effect=None):
    """
    Build a context-manager mock that mimics ``websockets.sync.client.connect``.

    Returns ``(factory, ws)`` so tests can both patch ``ws_connect`` and inspect calls
    made on the underlying websocket.
    """
    ws = MagicMock()
    if recv_side_effect is not None:
        ws.recv.side_effect = recv_side_effect
    else:
        ws.recv.return_value = recv_value
    ctx = MagicMock()
    ctx.__enter__.return_value = ws
    ctx.__exit__.return_value = False
    return MagicMock(return_value=ctx), ws


def _httpx_post_mock(response_body=None, status_code=200, side_effect=None):
    """Build a mock for ``httpx.post`` returning a response with the given JSON body."""
    if side_effect is not None:
        return MagicMock(side_effect=side_effect)
    response = MagicMock()
    response.json.return_value = response_body if response_body is not None else {}
    response.status_code = status_code
    response.raise_for_status = MagicMock()
    return MagicMock(return_value=response)


def _envelope(topic, payload):
    return json.dumps(
        {
            "fqcn": "test.pub.chnl",
            "topicName": topic,
            "topicVersion": "1.0.0",
            "topicOwner": "ddhub.test",
            "transactionId": "tx-id",
            "payload": json.dumps(payload),
        }
    )


class TestAuthHeaders:

    @staticmethod
    def test_returns_api_key_from_env():
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        assert conn._auth_headers() == {"x-api-key": "test-api-key"}

    @staticmethod
    def test_raises_when_env_var_missing(monkeypatch):
        monkeypatch.delenv("EW_CLIENT_GATEWAY_API_KEY", raising=False)
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        with pytest.raises(EnvironmentError):
            conn._auth_headers()


class TestPostBid:

    @staticmethod
    def test_returns_client_gateway_message_id():
        post = _httpx_post_mock(response_body={"clientGatewayMessageId": "msg-123"})
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        with patch("gsy_e.external.proxy.ewcg_connection.httpx.post", post):
            result = conn.post_bid(MARKET_ID, DELIVERY_START, 1.0, Decimal("20"))
        assert result == "msg-123"

    @staticmethod
    def test_envelope_carries_order_topic_metadata():
        post = _httpx_post_mock(response_body={"clientGatewayMessageId": "msg-123"})
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        with patch("gsy_e.external.proxy.ewcg_connection.httpx.post", post):
            conn.post_bid(MARKET_ID, DELIVERY_START, 1.5, Decimal("20"))

        envelope = post.call_args.kwargs["json"]
        assert envelope["topicName"] == ORDER_TOPIC
        assert envelope["topicVersion"] == "1.0.0"
        assert "transactionId" in envelope
        assert envelope["anonymousRecipient"] == []
        assert post.call_args.kwargs["headers"] == {"x-api-key": "test-api-key"}

    @staticmethod
    def test_payload_has_expected_bid_fields():
        post = _httpx_post_mock(response_body={"clientGatewayMessageId": "msg-123"})
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        with patch("gsy_e.external.proxy.ewcg_connection.httpx.post", post):
            conn.post_bid(MARKET_ID, DELIVERY_START, 1.5, Decimal("20"))

        envelope = post.call_args.kwargs["json"]
        payload = json.loads(envelope["payload"])
        assert payload["int:orderType"] == "Bid"
        assert payload["int:marketId"] == MARKET_ID
        assert payload["int:quantity"] == 1.5
        assert payload["int:priceLimit"] == 20.0
        assert payload["int:timeSlot"] == int(DELIVERY_START.timestamp())
        # NOTE: post_bid currently emits "createdBy" while post_offer emits
        # "int:createdBy". This test pins current behaviour — see TestPostOffer.
        actor = payload["createdBy"]["int:Actor"]
        assert actor["int:actorName"] == "trader-1"
        assert actor["int:actorType"] == "Prosumer"

    @staticmethod
    def test_returns_none_on_http_failure():
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        post = _httpx_post_mock(side_effect=httpx.ConnectError("boom"))
        with patch("gsy_e.external.proxy.ewcg_connection.httpx.post", post):
            assert conn.post_bid(MARKET_ID, DELIVERY_START, 1.0, Decimal("20")) is None

    @staticmethod
    def test_returns_none_when_response_lacks_message_id():
        post = _httpx_post_mock(response_body={"unrelated": "field"})
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        with patch("gsy_e.external.proxy.ewcg_connection.httpx.post", post):
            assert conn.post_bid(MARKET_ID, DELIVERY_START, 1.0, Decimal("20")) is None


class TestPostOffer:

    @staticmethod
    def test_returns_client_gateway_message_id():
        post = _httpx_post_mock(response_body={"clientGatewayMessageId": "msg-456"})
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        with patch("gsy_e.external.proxy.ewcg_connection.httpx.post", post):
            result = conn.post_offer(MARKET_ID, DELIVERY_START, 2.0, Decimal("30"))
        assert result == "msg-456"

    @staticmethod
    def test_payload_has_expected_offer_fields():
        post = _httpx_post_mock(response_body={"clientGatewayMessageId": "msg-456"})
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        with patch("gsy_e.external.proxy.ewcg_connection.httpx.post", post):
            conn.post_offer(MARKET_ID, DELIVERY_START, 2.0, Decimal("30"))

        envelope = post.call_args.kwargs["json"]
        payload = json.loads(envelope["payload"])
        assert payload["int:orderType"] == "Offer"
        assert payload["int:marketId"] == MARKET_ID
        assert payload["int:quantity"] == 2.0
        assert payload["int:priceLimit"] == 30.0
        assert payload["int:timeSlot"] == int(DELIVERY_START.timestamp())
        # post_offer uses the prefixed key — see note in TestPostBid.
        actor = payload["int:createdBy"]["int:Actor"]
        assert actor["int:actorName"] == "trader-1"
        assert actor["int:actorType"] == "Prosumer"


class TestDeleteOrder:

    @staticmethod
    def test_delete_bid_sends_expected_payload():
        post = _httpx_post_mock(response_body={})
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        with patch("gsy_e.external.proxy.ewcg_connection.httpx.post", post):
            conn.delete_bid(DELIVERY_START, "bid-id-001")

        envelope = post.call_args.kwargs["json"]
        payload = json.loads(envelope["payload"])
        assert payload == {
            "int:orderId": "bid-id-001",
            "int:orderType": "Bid",
            "int:timeSlot": int(DELIVERY_START.timestamp()),
        }

    @staticmethod
    def test_delete_offer_sends_expected_payload():
        post = _httpx_post_mock(response_body={})
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        with patch("gsy_e.external.proxy.ewcg_connection.httpx.post", post):
            conn.delete_offer(DELIVERY_START, "offer-id-001")

        envelope = post.call_args.kwargs["json"]
        payload = json.loads(envelope["payload"])
        assert payload == {
            "int:orderId": "offer-id-001",
            "int:orderType": "Offer",
            "int:timeSlot": int(DELIVERY_START.timestamp()),
        }


class TestParseHelpers:

    @staticmethod
    def test_parse_market_slot_round_trip():
        data = {
            "int:marketId": MARKET_ID,
            "int:communityId": COMMUNITY_ID,
            "int:openingTime": SLOT_OPEN.isoformat(),
            "int:closingTime": SLOT_CLOSE.isoformat(),
            "int:deliveryStartTime": DELIVERY_START.isoformat(),
            "int:deliveryEndTime": DELIVERY_END.isoformat(),
            "int:marketType": MarketType.SPOT.value,
        }
        info = EWClientGatewayConnection._parse_market_slot(data)
        assert isinstance(info, MarketSlotInfo)
        assert info.market_id == MARKET_ID
        assert info.community_id == COMMUNITY_ID
        assert info.opening_time == SLOT_OPEN
        assert info.closing_time == SLOT_CLOSE
        assert info.delivery_start_time == DELIVERY_START
        assert info.delivery_end_time == DELIVERY_END
        assert info.market_type == MarketType.SPOT

    @staticmethod
    def test_parse_market_slot_decodes_market_type():
        data = {
            "int:marketId": MARKET_ID,
            "int:communityId": COMMUNITY_ID,
            "int:openingTime": SLOT_OPEN.isoformat(),
            "int:closingTime": SLOT_CLOSE.isoformat(),
            "int:deliveryStartTime": DELIVERY_START.isoformat(),
            "int:deliveryEndTime": DELIVERY_END.isoformat(),
            "int:marketType": MarketType.FLEXIBILITY.value,
        }
        info = EWClientGatewayConnection._parse_market_slot(data)
        assert info.market_type == MarketType.FLEXIBILITY

    @staticmethod
    def test_parse_trade_round_trip():
        data = {
            "int:marketId": MARKET_ID,
            "int:offerId": "offer-1",
            "int:bidId": "bid-1",
            "int:price": 12.5,
            "int:energyKWh": 1.25,
            "int:seller": "alice",
            "int:buyer": "bob",
            "int:residualOfferId": "res-offer-1",
            "int:residualBidId": "res-bid-1",
        }
        trade = EWClientGatewayConnection._parse_trade(data)
        assert isinstance(trade, EnergyTrade)
        assert trade.market_id == MARKET_ID
        assert trade.offer_id == "offer-1"
        assert trade.bid_id == "bid-1"
        assert trade.price == 12.5
        assert trade.energy_kWh == 1.25
        assert trade.seller == "alice"
        assert trade.buyer == "bob"
        assert trade.residual_offer_id == "res-offer-1"
        assert trade.residual_bid_id == "res-bid-1"

    @staticmethod
    def test_parse_trade_residual_ids_optional():
        data = {
            "int:marketId": MARKET_ID,
            "int:offerId": "offer-1",
            "int:bidId": "bid-1",
            "int:price": 0.0,
            "int:energyKWh": 0.0,
            "int:seller": "alice",
            "int:buyer": "bob",
        }
        trade = EWClientGatewayConnection._parse_trade(data)
        assert trade.residual_offer_id is None
        assert trade.residual_bid_id is None


def _stop_after(messages, conn):
    """
    Build a recv side_effect that yields each message once, then sets stop_event
    and raises TimeoutError so the listener loop exits cleanly at the next iteration.
    """
    iterator = iter(messages)

    def recv(timeout=None):  # pylint: disable=unused-argument
        try:
            return next(iterator)
        except StopIteration as exc:
            conn._stop_event.set()
            raise TimeoutError from exc

    return recv


class TestListener:

    @staticmethod
    def test_dispatches_market_slot_to_callback():
        on_market_slot = MagicMock()
        on_trade = MagicMock()
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        slot_payload = {
            "int:marketId": MARKET_ID,
            "int:communityId": COMMUNITY_ID,
            "int:openingTime": SLOT_OPEN.isoformat(),
            "int:closingTime": SLOT_CLOSE.isoformat(),
            "int:deliveryStartTime": DELIVERY_START.isoformat(),
            "int:deliveryEndTime": DELIVERY_END.isoformat(),
            "int:marketType": MarketType.SPOT.value,
        }
        factory, _ws = _ws_factory(
            recv_side_effect=_stop_after([_envelope(MARKET_SLOT_TOPIC, slot_payload)], conn)
        )
        with patch("gsy_e.external.proxy.ewcg_connection.ws_connect", factory):
            conn._listener(on_market_slot, on_trade)

        on_market_slot.assert_called_once()
        assert on_market_slot.call_args[0][0].market_id == MARKET_ID
        on_trade.assert_not_called()

    @staticmethod
    def test_dispatches_trade_to_callback():
        on_market_slot = MagicMock()
        on_trade = MagicMock()
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        trade_payload = {
            "int:marketId": MARKET_ID,
            "int:offerId": "offer-1",
            "int:bidId": "bid-1",
            "int:price": 1.0,
            "int:energyKWh": 0.5,
            "int:seller": "alice",
            "int:buyer": "bob",
        }
        factory, _ws = _ws_factory(
            recv_side_effect=_stop_after([_envelope(TRADE_TOPIC, trade_payload)], conn)
        )
        with patch("gsy_e.external.proxy.ewcg_connection.ws_connect", factory):
            conn._listener(on_market_slot, on_trade)

        on_trade.assert_called_once()
        assert on_trade.call_args[0][0].market_id == MARKET_ID
        on_market_slot.assert_not_called()

    @staticmethod
    def test_ignores_unknown_topic():
        on_market_slot = MagicMock()
        on_trade = MagicMock()
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        factory, _ws = _ws_factory(
            recv_side_effect=_stop_after([_envelope("some.other.topic", {"foo": "bar"})], conn)
        )
        with patch("gsy_e.external.proxy.ewcg_connection.ws_connect", factory):
            conn._listener(on_market_slot, on_trade)

        on_market_slot.assert_not_called()
        on_trade.assert_not_called()

    @staticmethod
    def test_swallows_malformed_payload_and_continues():
        on_market_slot = MagicMock()
        on_trade = MagicMock()
        conn = EWClientGatewayConnection("trader-1", "Prosumer")

        # First message is junk (will fail json.loads on payload), second is valid.
        bad_envelope = json.dumps({"topicName": MARKET_SLOT_TOPIC, "payload": "not-json"})
        good_payload = {
            "int:marketId": MARKET_ID,
            "int:communityId": COMMUNITY_ID,
            "int:openingTime": SLOT_OPEN.isoformat(),
            "int:closingTime": SLOT_CLOSE.isoformat(),
            "int:deliveryStartTime": DELIVERY_START.isoformat(),
            "int:deliveryEndTime": DELIVERY_END.isoformat(),
            "int:marketType": MarketType.SPOT.value,
        }
        factory, _ws = _ws_factory(
            recv_side_effect=_stop_after(
                [bad_envelope, _envelope(MARKET_SLOT_TOPIC, good_payload)], conn
            )
        )
        with patch("gsy_e.external.proxy.ewcg_connection.ws_connect", factory):
            conn._listener(on_market_slot, on_trade)

        on_market_slot.assert_called_once()
        on_trade.assert_not_called()

    @staticmethod
    def test_timeout_does_not_terminate_loop():
        on_market_slot = MagicMock()
        on_trade = MagicMock()
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        slot_payload = {
            "int:marketId": MARKET_ID,
            "int:communityId": COMMUNITY_ID,
            "int:openingTime": SLOT_OPEN.isoformat(),
            "int:closingTime": SLOT_CLOSE.isoformat(),
            "int:deliveryStartTime": DELIVERY_START.isoformat(),
            "int:deliveryEndTime": DELIVERY_END.isoformat(),
            "int:marketType": MarketType.SPOT.value,
        }

        iterator = iter([TimeoutError(), _envelope(MARKET_SLOT_TOPIC, slot_payload)])

        def recv(timeout=None):  # pylint: disable=unused-argument
            try:
                value = next(iterator)
            except StopIteration as exc:
                conn._stop_event.set()
                raise TimeoutError from exc
            if isinstance(value, BaseException):
                raise value
            return value

        factory, _ws = _ws_factory(recv_side_effect=recv)
        with patch("gsy_e.external.proxy.ewcg_connection.ws_connect", factory):
            conn._listener(on_market_slot, on_trade)

        on_market_slot.assert_called_once()


class TestSubscribe:

    @staticmethod
    def test_starts_background_thread():
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        with patch.object(conn, "_listener") as mock_listener:
            mock_listener.side_effect = lambda *a, **kw: conn._stop_event.wait()
            conn.subscribe(on_market_slot=MagicMock(), on_trade=MagicMock())
            assert conn._subscription_thread is not None
            assert conn._subscription_thread.is_alive()
            conn.stop_subscription()

        assert conn._subscription_thread is None

    @staticmethod
    def test_second_subscribe_is_noop_when_thread_alive():
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        with patch.object(conn, "_listener") as mock_listener:
            mock_listener.side_effect = lambda *a, **kw: conn._stop_event.wait()
            conn.subscribe(on_market_slot=MagicMock(), on_trade=MagicMock())
            first_thread = conn._subscription_thread
            conn.subscribe(on_market_slot=MagicMock(), on_trade=MagicMock())
            assert conn._subscription_thread is first_thread
            conn.stop_subscription()

    @staticmethod
    def test_stop_subscription_joins_thread():
        conn = EWClientGatewayConnection("trader-1", "Prosumer")
        started = threading.Event()

        def fake_listener(*_args, **_kwargs):
            started.set()
            conn._stop_event.wait()

        with patch.object(conn, "_listener", side_effect=fake_listener):
            conn.subscribe(on_market_slot=MagicMock(), on_trade=MagicMock())
            assert started.wait(timeout=2.0)
            conn.stop_subscription()

        assert conn._subscription_thread is None
        assert conn._stop_event.is_set()
