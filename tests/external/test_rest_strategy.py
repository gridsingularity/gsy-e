# pylint: disable=missing-function-docstring, protected-access, missing-class-docstring
"""Unit tests for RestExternalStrategy in gsy_e.external.rest_strategy."""
import threading
from unittest.mock import MagicMock, patch

import pendulum
import pytest
from fastapi.testclient import TestClient
from gsy_framework.enums import AvailableMarketTypes

from gsy_e.external.external_strategy import ExternalOrderInput
from gsy_e.external.rest_strategy import (
    OrderInputRequest,
    RestExternalStrategy,
    RestStrategyServer,
    configure_rest_server,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SLOT_START = pendulum.datetime(2024, 1, 1, 12, 0, tz="UTC")
SLOT_START_ISO = SLOT_START.isoformat()


def make_order_request(
    energy_kWh=1.0,
    min_price=10.0,
    max_price=50.0,
    market_type="SPOT",
    time_slot=SLOT_START_ISO,
) -> OrderInputRequest:
    return OrderInputRequest(
        energy_kWh=energy_kWh,
        min_price=min_price,
        max_price=max_price,
        market_type=market_type,
        time_slot=time_slot,
    )


def make_external_order_input(
    energy_kWh=1.0, min_price=10.0, max_price=50.0
) -> ExternalOrderInput:
    return ExternalOrderInput(
        energy_kWh=energy_kWh,
        min_price=min_price,
        max_price=max_price,
        market_type=AvailableMarketTypes.SPOT,
        time_slot=SLOT_START,
    )


def make_strategy(bid_inputs=None, offer_inputs=None, area_name="house-1") -> RestExternalStrategy:
    strategy = RestExternalStrategy(
        bid_inputs=bid_inputs,
        offer_inputs=offer_inputs,
    )
    area_mock = MagicMock()
    area_mock.now = SLOT_START
    area_mock.name = area_name
    strategy.area = area_mock
    strategy._dispatcher = MagicMock()
    return strategy


@pytest.fixture(autouse=True)
def _reset_server_singleton():
    """Ensure each test starts with a fresh, unstarted RestStrategyServer."""
    RestStrategyServer._instance = None
    yield
    srv = RestStrategyServer._instance
    if srv is not None and srv._uvicorn_server is not None:
        srv._stop_server()
    RestStrategyServer._instance = None


# ---------------------------------------------------------------------------
# Tests: OrderInputRequest schema
# ---------------------------------------------------------------------------


class TestOrderInputRequest:

    @staticmethod
    def test_to_external_order_input_parses_correctly():
        req = make_order_request()
        inp = req.to_external_order_input()
        assert inp.energy_kWh == 1.0
        assert inp.min_price == 10.0
        assert inp.max_price == 50.0
        assert inp.market_type == AvailableMarketTypes.SPOT
        assert inp.time_slot == SLOT_START

    @staticmethod
    def test_from_external_order_input_round_trips():
        original = make_external_order_input()
        req = OrderInputRequest.from_external_order_input(original)
        assert req.energy_kWh == original.energy_kWh
        assert req.min_price == original.min_price
        assert req.max_price == original.max_price
        assert req.market_type == original.market_type.name
        restored = req.to_external_order_input()
        assert restored.energy_kWh == original.energy_kWh
        assert restored.market_type == original.market_type
        assert restored.time_slot == original.time_slot

    @staticmethod
    def test_to_external_order_input_case_insensitive_market_type():
        req = make_order_request(market_type="spot")
        inp = req.to_external_order_input()
        assert inp.market_type == AvailableMarketTypes.SPOT


# ---------------------------------------------------------------------------
# Tests: REST endpoints via TestClient
# ---------------------------------------------------------------------------


class TestRestEndpoints:

    @pytest.fixture()
    def client(self):
        server = RestStrategyServer.instance()
        strategy = make_strategy(area_name="house-1")
        server._strategies["house-1"] = strategy
        return TestClient(server._app), strategy, server

    def test_put_bids_replaces_pending_inputs(self, client):
        tc, strategy, _ = client
        payload = [
            {
                "energy_kWh": 2.0,
                "min_price": 5.0,
                "max_price": 30.0,
                "market_type": "SPOT",
                "time_slot": SLOT_START_ISO,
            }
        ]
        response = tc.put("/house-1/bids", json=payload)
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "count": 1}
        assert len(strategy._pending_bid_inputs) == 1
        assert strategy._pending_bid_inputs[0].energy_kWh == 2.0

    def test_put_offers_replaces_pending_inputs(self, client):
        tc, strategy, _ = client
        payload = [
            {
                "energy_kWh": 3.0,
                "min_price": 5.0,
                "max_price": 40.0,
                "market_type": "SPOT",
                "time_slot": SLOT_START_ISO,
            }
        ]
        response = tc.put("/house-1/offers", json=payload)
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "count": 1}
        assert len(strategy._pending_offer_inputs) == 1
        assert strategy._pending_offer_inputs[0].energy_kWh == 3.0

    def test_put_bids_with_empty_list_clears_inputs(self, client):
        tc, strategy, _ = client
        strategy._pending_bid_inputs = [make_external_order_input()]
        response = tc.put("/house-1/bids", json=[])
        assert response.status_code == 200
        assert strategy._pending_bid_inputs == []

    def test_get_bids_returns_current_pending(self, client):
        tc, strategy, _ = client
        strategy._pending_bid_inputs = [make_external_order_input(energy_kWh=5.0)]
        response = tc.get("/house-1/bids")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["energy_kWh"] == 5.0
        assert data[0]["market_type"] == "SPOT"

    def test_get_offers_returns_current_pending(self, client):
        tc, strategy, _ = client
        strategy._pending_offer_inputs = [make_external_order_input(energy_kWh=7.0)]
        response = tc.get("/house-1/offers")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["energy_kWh"] == 7.0

    def test_put_bids_with_multiple_inputs(self, client):
        tc, strategy, _ = client
        payload = [
            {
                "energy_kWh": 1.0,
                "min_price": 5.0,
                "max_price": 20.0,
                "market_type": "SPOT",
                "time_slot": SLOT_START_ISO,
            },
            {
                "energy_kWh": 2.0,
                "min_price": 8.0,
                "max_price": 25.0,
                "market_type": "SPOT",
                "time_slot": SLOT_START_ISO,
            },
        ]
        response = tc.put("/house-1/bids", json=payload)
        assert response.json() == {"status": "ok", "count": 2}
        assert len(strategy._pending_bid_inputs) == 2

    def test_put_bids_unknown_area_returns_404(self, client):
        tc, _, _ = client
        response = tc.put(
            "/unknown-area/bids",
            json=[
                {
                    "energy_kWh": 1.0,
                    "min_price": 5.0,
                    "max_price": 20.0,
                    "market_type": "SPOT",
                    "time_slot": SLOT_START_ISO,
                }
            ],
        )
        assert response.status_code == 404

    def test_routes_dispatch_by_area_name(self):
        server = RestStrategyServer.instance()
        strategy_a = make_strategy(area_name="house-A")
        strategy_b = make_strategy(area_name="house-B")
        server._strategies["house-A"] = strategy_a
        server._strategies["house-B"] = strategy_b
        tc = TestClient(server._app)

        payload_a = [
            {
                "energy_kWh": 1.0,
                "min_price": 1.0,
                "max_price": 10.0,
                "market_type": "SPOT",
                "time_slot": SLOT_START_ISO,
            }
        ]
        payload_b = [
            {
                "energy_kWh": 2.0,
                "min_price": 2.0,
                "max_price": 20.0,
                "market_type": "SPOT",
                "time_slot": SLOT_START_ISO,
            }
        ]
        tc.put("/house-A/bids", json=payload_a)
        tc.put("/house-B/bids", json=payload_b)

        assert strategy_a._pending_bid_inputs[0].energy_kWh == 1.0
        assert strategy_b._pending_bid_inputs[0].energy_kWh == 2.0


# ---------------------------------------------------------------------------
# Tests: event_market_cycle flushes pending inputs
# ---------------------------------------------------------------------------


class TestRestExternalStrategyMarketCycle:

    @staticmethod
    def test_event_market_cycle_applies_pending_bids():
        strategy = make_strategy()
        strategy._pending_bid_inputs = [make_external_order_input(energy_kWh=4.0)]
        spot_market = MagicMock()
        spot_market.time_slot = SLOT_START
        spot_market.get_market_parameters_for_market_slot.return_value = None
        strategy.area.spot_market = spot_market

        strategy.event_market_cycle()

        assert strategy._bid_inputs[0].energy_kWh == 4.0

    @staticmethod
    def test_event_market_cycle_applies_pending_offers():
        strategy = make_strategy()
        strategy._pending_offer_inputs = [make_external_order_input(energy_kWh=6.0)]
        spot_market = MagicMock()
        spot_market.time_slot = SLOT_START
        spot_market.get_market_parameters_for_market_slot.return_value = None
        strategy.area.spot_market = spot_market

        strategy.event_market_cycle()

        assert strategy._offer_inputs[0].energy_kWh == 6.0

    @staticmethod
    def test_event_market_cycle_does_not_mutate_pending_list():
        """The strategy's internal list must be a copy, not the same object."""
        strategy = make_strategy()
        pending = [make_external_order_input()]
        strategy._pending_bid_inputs = pending
        spot_market = MagicMock()
        spot_market.time_slot = SLOT_START
        spot_market.get_market_parameters_for_market_slot.return_value = None
        strategy.area.spot_market = spot_market

        strategy.event_market_cycle()

        # The active list is a copy so mutating the pending list has no side-effect.
        assert strategy._bid_inputs is not pending


# ---------------------------------------------------------------------------
# Tests: registration and shared server lifecycle
# ---------------------------------------------------------------------------


class TestRestStrategyServerRegistration:

    @staticmethod
    def test_event_activate_registers_strategy_with_shared_server():
        strategy = make_strategy(area_name="area-x")
        with patch.object(RestStrategyServer, "_start_server"):
            strategy.event_activate()
        assert RestStrategyServer.instance()._strategies["area-x"] is strategy

    @staticmethod
    def test_event_deactivate_deregisters_strategy():
        strategy = make_strategy(area_name="area-x")
        with patch.object(RestStrategyServer, "_start_server"), patch.object(
            RestStrategyServer, "_stop_server"
        ):
            strategy.event_activate()
            strategy.event_deactivate()
        assert "area-x" not in RestStrategyServer.instance()._strategies

    @staticmethod
    def test_first_registration_starts_server_subsequent_do_not():
        server = RestStrategyServer.instance()
        strategy_a = make_strategy(area_name="a")
        strategy_b = make_strategy(area_name="b")
        with patch.object(server, "_start_server") as mock_start:
            server.register("a", strategy_a)
            # Simulate a running server so the second register() does not start it.
            server._uvicorn_server = MagicMock()
            server.register("b", strategy_b)
            assert mock_start.call_count == 1

    @staticmethod
    def test_last_deregistration_stops_server():
        server = RestStrategyServer.instance()
        strategy_a = make_strategy(area_name="a")
        strategy_b = make_strategy(area_name="b")
        server._strategies = {"a": strategy_a, "b": strategy_b}
        server._uvicorn_server = MagicMock()
        with patch.object(server, "_stop_server") as mock_stop:
            server.deregister("a")
            assert mock_stop.call_count == 0
            server.deregister("b")
            assert mock_stop.call_count == 1

    @staticmethod
    def test_duplicate_registration_with_different_strategy_raises():
        server = RestStrategyServer.instance()
        strategy_a = make_strategy(area_name="a")
        strategy_a2 = make_strategy(area_name="a")
        with patch.object(server, "_start_server"):
            server.register("a", strategy_a)
            with pytest.raises(ValueError):
                server.register("a", strategy_a2)


class TestRestStrategyServerLifecycle:

    @staticmethod
    def test_start_server_spawns_daemon_thread():
        server = RestStrategyServer(host="127.0.0.1", port=19999)
        mock_server = MagicMock()
        started = threading.Event()
        block = threading.Event()

        def slow_run():
            started.set()
            block.wait(timeout=2)

        mock_server.run = slow_run
        with patch("uvicorn.Server", return_value=mock_server):
            server._start_server()
            started.wait(timeout=2)
            assert server._server_thread is not None
            assert server._server_thread.daemon is True
            assert server._server_thread.is_alive()
        block.set()
        server._server_thread.join(timeout=2)

    @staticmethod
    def test_stop_server_signals_exit_and_joins():
        server = RestStrategyServer()
        mock_thread = MagicMock(spec=threading.Thread)
        server._server_thread = mock_thread
        mock_uvicorn = MagicMock()
        server._uvicorn_server = mock_uvicorn

        server._stop_server()

        assert mock_uvicorn.should_exit is True
        mock_thread.join.assert_called_once_with(timeout=5)
        assert server._uvicorn_server is None
        assert server._server_thread is None


class TestConfigureRestServer:

    @staticmethod
    def test_configure_rest_server_sets_host_and_port():
        server = configure_rest_server(host="127.0.0.1", port=9000)
        assert server is RestStrategyServer.instance()
        assert server._host == "127.0.0.1"
        assert server._port == 9000

    @staticmethod
    def test_configure_rest_server_raises_after_startup():
        server = RestStrategyServer.instance()
        server._uvicorn_server = MagicMock()  # simulate running
        with pytest.raises(RuntimeError):
            configure_rest_server(host="127.0.0.1", port=9001)
