# pylint: disable=missing-function-docstring, protected-access, missing-class-docstring
"""Unit tests for RestExternalStrategy in gsy_e.external.rest_strategy."""
import threading
from unittest.mock import MagicMock, patch

import pendulum
import pytest
from fastapi.testclient import TestClient
from gsy_framework.enums import AvailableMarketTypes

from gsy_e.external.external_strategy import ExternalOrderInput
from gsy_e.external.rest_strategy import OrderInputRequest, RestExternalStrategy


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


def make_strategy(bid_inputs=None, offer_inputs=None, rest_port=8099) -> RestExternalStrategy:
    strategy = RestExternalStrategy(
        bid_inputs=bid_inputs,
        offer_inputs=offer_inputs,
        rest_port=rest_port,
    )
    area_mock = MagicMock()
    area_mock.now = SLOT_START
    strategy.area = area_mock
    strategy._dispatcher = MagicMock()
    return strategy


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
        strategy = make_strategy()
        return TestClient(strategy._app), strategy

    def test_put_bids_replaces_pending_inputs(self, client):
        tc, strategy = client
        payload = [
            {
                "energy_kWh": 2.0,
                "min_price": 5.0,
                "max_price": 30.0,
                "market_type": "SPOT",
                "time_slot": SLOT_START_ISO,
            }
        ]
        response = tc.put("/bids", json=payload)
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "count": 1}
        assert len(strategy._pending_bid_inputs) == 1
        assert strategy._pending_bid_inputs[0].energy_kWh == 2.0

    def test_put_offers_replaces_pending_inputs(self, client):
        tc, strategy = client
        payload = [
            {
                "energy_kWh": 3.0,
                "min_price": 5.0,
                "max_price": 40.0,
                "market_type": "SPOT",
                "time_slot": SLOT_START_ISO,
            }
        ]
        response = tc.put("/offers", json=payload)
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "count": 1}
        assert len(strategy._pending_offer_inputs) == 1
        assert strategy._pending_offer_inputs[0].energy_kWh == 3.0

    def test_put_bids_with_empty_list_clears_inputs(self, client):
        tc, strategy = client
        strategy._pending_bid_inputs = [make_external_order_input()]
        response = tc.put("/bids", json=[])
        assert response.status_code == 200
        assert strategy._pending_bid_inputs == []

    def test_get_bids_returns_current_pending(self, client):
        tc, strategy = client
        strategy._pending_bid_inputs = [make_external_order_input(energy_kWh=5.0)]
        response = tc.get("/bids")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["energy_kWh"] == 5.0
        assert data[0]["market_type"] == "SPOT"

    def test_get_offers_returns_current_pending(self, client):
        tc, strategy = client
        strategy._pending_offer_inputs = [make_external_order_input(energy_kWh=7.0)]
        response = tc.get("/offers")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["energy_kWh"] == 7.0

    def test_put_bids_with_multiple_inputs(self, client):
        tc, strategy = client
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
        response = tc.put("/bids", json=payload)
        assert response.json() == {"status": "ok", "count": 2}
        assert len(strategy._pending_bid_inputs) == 2


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
# Tests: server thread management
# ---------------------------------------------------------------------------


class TestRestExternalStrategyServerThread:

    @staticmethod
    def test_event_activate_starts_server_thread():
        strategy = make_strategy()
        with patch.object(strategy, "_start_server") as mock_start:
            strategy.event_activate()
            mock_start.assert_called_once()

    @staticmethod
    def test_event_deactivate_stops_server():
        strategy = make_strategy()
        with patch.object(strategy, "_stop_server") as mock_stop:
            strategy.event_deactivate()
            mock_stop.assert_called_once()

    @staticmethod
    def test_start_server_spawns_daemon_thread():
        strategy = make_strategy(rest_port=19999)
        mock_server = MagicMock()
        # Block run() until we release the event so the thread stays alive long
        # enough to inspect its properties.
        started = threading.Event()
        block = threading.Event()

        def slow_run():
            started.set()
            block.wait(timeout=2)

        mock_server.run = slow_run
        with patch("uvicorn.Server", return_value=mock_server):
            strategy._start_server()
            started.wait(timeout=2)
            assert strategy._server_thread is not None
            assert strategy._server_thread.daemon is True
            assert strategy._server_thread.is_alive()
        block.set()
        strategy._server_thread.join(timeout=2)

    @staticmethod
    def test_stop_server_signals_exit_and_joins():
        strategy = make_strategy()
        mock_thread = MagicMock(spec=threading.Thread)
        strategy._server_thread = mock_thread
        mock_uvicorn = MagicMock()
        strategy._uvicorn_server = mock_uvicorn

        strategy._stop_server()

        assert mock_uvicorn.should_exit is True
        mock_thread.join.assert_called_once_with(timeout=5)
