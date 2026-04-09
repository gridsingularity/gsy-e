"""
REST API extension for ExternalStrategyBase.

Starts a FastAPI server in a background daemon thread so that bids and offers
can be submitted over HTTP while a gsy-e simulation is running.  Incoming
inputs are buffered behind a lock and flushed into the strategy at the
beginning of every market cycle.
"""

from __future__ import annotations

import logging
import threading
from typing import List, Optional

import pendulum
import uvicorn
from fastapi import FastAPI
from gsy_framework.enums import AvailableMarketTypes
from pydantic import BaseModel, Field

from gsy_e.external.external_strategy import ExternalOrderInput, ExternalStrategyBase

logger = logging.getLogger(__name__)


class OrderInputRequest(BaseModel):
    """HTTP request body for a single bid or offer input."""

    energy_kWh: float = Field(..., gt=0, description="Energy amount in kWh.")
    min_price: float = Field(..., ge=0, description="Lower bound of the price range.")
    max_price: float = Field(..., ge=0, description="Upper bound of the price range.")
    market_type: str = Field(
        default="SPOT",
        description=(
            "Target market type. " f"Allowed values: {[e.name for e in AvailableMarketTypes]}."
        ),
    )
    time_slot: str = Field(
        ...,
        description="Delivery time slot in ISO 8601 format (e.g. '2024-01-01T12:00:00+00:00').",
    )

    def to_external_order_input(self) -> ExternalOrderInput:
        """Parse into an ExternalOrderInput."""
        return ExternalOrderInput(
            energy_kWh=self.energy_kWh,
            min_price=self.min_price,
            max_price=self.max_price,
            # pylint: disable=no-member
            market_type=AvailableMarketTypes[self.market_type.upper()],
            time_slot=pendulum.parse(self.time_slot),
        )

    @staticmethod
    def from_external_order_input(inp: ExternalOrderInput) -> "OrderInputRequest":
        """Convert an ExternalOrderInput back to a serialisable request object."""
        return OrderInputRequest(
            energy_kWh=inp.energy_kWh,
            min_price=inp.min_price,
            max_price=inp.max_price,
            market_type=inp.market_type.name,
            time_slot=inp.time_slot.isoformat(),
        )


# pylint: disable=too-many-instance-attributes
class RestExternalStrategy(ExternalStrategyBase):
    """
    ExternalStrategyBase extended with a FastAPI REST server.

    The server runs in a background daemon thread and exposes two endpoints:

    * ``PUT /bids``  – replace the pending bid inputs (list of :class:`OrderInputRequest`).
    * ``PUT /offers`` – replace the pending offer inputs.
    * ``GET /bids``  – return the currently pending bid inputs.
    * ``GET /offers`` – return the currently pending offer inputs.

    At the start of each market cycle the pending inputs are consumed and forwarded to
    :meth:`update_bid_inputs` / :meth:`update_offer_inputs` before the parent cycle logic runs.

    Args:
        bid_inputs: Initial bid inputs (optional).
        offer_inputs: Initial offer inputs (optional).
        rest_host: Host address the server should bind to (default ``"0.0.0.0"``).
        rest_port: TCP port the server should listen on (default ``8080``).
    """

    def __init__(
        self,
        bid_inputs: Optional[List[ExternalOrderInput]] = None,
        offer_inputs: Optional[List[ExternalOrderInput]] = None,
        rest_host: str = "0.0.0.0",
        rest_port: int = 8080,
    ) -> None:
        super().__init__(bid_inputs=bid_inputs, offer_inputs=offer_inputs)
        self._rest_host = rest_host
        self._rest_port = rest_port

        # Pending inputs written by the REST thread and consumed by the sim thread.
        self._lock = threading.Lock()
        self._pending_bid_inputs: List[ExternalOrderInput] = list(bid_inputs or [])
        self._pending_offer_inputs: List[ExternalOrderInput] = list(offer_inputs or [])

        self._uvicorn_server: Optional[uvicorn.Server] = None
        self._server_thread: Optional[threading.Thread] = None
        self._app: FastAPI = self._build_app()

    # ------------------------------------------------------------------
    # gsy-e lifecycle hooks
    # ------------------------------------------------------------------

    def event_activate(self, **kwargs) -> None:
        super().event_activate(**kwargs)
        self._start_server()

    def event_market_cycle(self) -> None:
        """Flush pending REST inputs, then run the normal market-cycle logic."""
        with self._lock:
            self.update_bid_inputs(list(self._pending_bid_inputs))
            self.update_offer_inputs(list(self._pending_offer_inputs))
        super().event_market_cycle()

    def event_deactivate(self) -> None:
        """Deactivate event, stops the Uvicorn server."""
        self._stop_server()

    def _start_server(self) -> None:
        config = uvicorn.Config(
            self._app,
            host=self._rest_host,
            port=self._rest_port,
            log_level="warning",
        )
        self._uvicorn_server = uvicorn.Server(config)
        self._server_thread = threading.Thread(
            target=self._uvicorn_server.run,
            name="RestExternalStrategy-API",
            daemon=True,
        )
        self._server_thread.start()
        logger.info("REST API server started on %s:%d", self._rest_host, self._rest_port)

    def _stop_server(self) -> None:
        if self._uvicorn_server is not None:
            self._uvicorn_server.should_exit = True
        if self._server_thread is not None:
            self._server_thread.join(timeout=5)
        logger.info("REST API server stopped")

    def _build_app(self) -> FastAPI:
        app = FastAPI(
            title="ExternalStrategy REST API",
            description=(
                "Submit bids and offers to the running gsy-e simulation. "
                "Inputs are applied at the start of the next market cycle."
            ),
        )

        @app.put("/bids", summary="Replace pending bid inputs")
        def put_bids(inputs: List[OrderInputRequest]) -> dict:
            parsed = [inp.to_external_order_input() for inp in inputs]
            with self._lock:
                self._pending_bid_inputs = parsed
            return {"status": "ok", "count": len(parsed)}

        @app.put("/offers", summary="Replace pending offer inputs")
        def put_offers(inputs: List[OrderInputRequest]) -> dict:
            parsed = [inp.to_external_order_input() for inp in inputs]
            with self._lock:
                self._pending_offer_inputs = parsed
            return {"status": "ok", "count": len(parsed)}

        @app.get("/bids", summary="Get current pending bid inputs")
        def get_bids() -> List[OrderInputRequest]:
            with self._lock:
                return [
                    OrderInputRequest.from_external_order_input(inp)
                    for inp in self._pending_bid_inputs
                ]

        @app.get("/offers", summary="Get current pending offer inputs")
        def get_offers() -> List[OrderInputRequest]:
            with self._lock:
                return [
                    OrderInputRequest.from_external_order_input(inp)
                    for inp in self._pending_offer_inputs
                ]

        return app
