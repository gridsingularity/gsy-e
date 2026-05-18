"""
REST API extension for ExternalStrategyBase.

A single FastAPI/uvicorn server is shared across every ``RestExternalStrategy``
instance in the running simulation. Endpoints are namespaced by area name, so
each incoming request is routed to the strategy whose ``area.name`` matches the
path parameter. The server is started lazily on the first registration and
stopped when the last strategy deregisters.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

import pendulum
import uvicorn
from fastapi import FastAPI, HTTPException
from gsy_framework.enums import AvailableMarketTypes
from pydantic import BaseModel, Field

from gsy_e.external.external_strategy import ExternalOrderInput, ExternalStrategyBase

logger = logging.getLogger(__name__)

DEFAULT_REST_HOST = "0.0.0.0"
DEFAULT_REST_PORT = 8080


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


class RestStrategyServer:
    """
    Shared FastAPI server that dispatches REST requests to the right strategy.

    Endpoints:

    * ``PUT /{area_name}/bids``   – replace pending bid inputs for an area.
    * ``PUT /{area_name}/offers`` – replace pending offer inputs for an area.
    * ``GET /{area_name}/bids``   – return pending bid inputs for an area.
    * ``GET /{area_name}/offers`` – return pending offer inputs for an area.
    """

    _instance: Optional["RestStrategyServer"] = None

    def __init__(self, host: str = DEFAULT_REST_HOST, port: int = DEFAULT_REST_PORT) -> None:
        self._host = host
        self._port = port
        self._registry_lock = threading.Lock()
        self._strategies: Dict[str, "RestExternalStrategy"] = {}
        self._uvicorn_server: Optional[uvicorn.Server] = None
        self._server_thread: Optional[threading.Thread] = None
        self._app: FastAPI = self._build_app()

    @classmethod
    def instance(cls) -> "RestStrategyServer":
        """Return the process-wide singleton, creating it with defaults if needed."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, area_name: str, strategy: "RestExternalStrategy") -> None:
        """Add a strategy to the registry and start the server if not already running."""
        with self._registry_lock:
            existing = self._strategies.get(area_name)
            if existing is not None and existing is not strategy:
                raise ValueError(
                    f"Area {area_name!r} is already registered with a different strategy."
                )
            self._strategies[area_name] = strategy
            if self._uvicorn_server is None:
                self._start_server()

    def deregister(self, area_name: str) -> None:
        """Remove a strategy from the registry, stopping the server if it was the last."""
        with self._registry_lock:
            self._strategies.pop(area_name, None)
            if not self._strategies:
                self._stop_server()

    def _start_server(self) -> None:
        config = uvicorn.Config(
            self._app,
            host=self._host,
            port=self._port,
            log_level="warning",
        )
        self._uvicorn_server = uvicorn.Server(config)
        self._server_thread = threading.Thread(
            target=self._uvicorn_server.run,
            name="RestStrategyServer",
            daemon=True,
        )
        self._server_thread.start()
        logger.info("REST strategy server started on %s:%d", self._host, self._port)

    def _stop_server(self) -> None:
        if self._uvicorn_server is not None:
            self._uvicorn_server.should_exit = True
        if self._server_thread is not None:
            self._server_thread.join(timeout=5)
        self._uvicorn_server = None
        self._server_thread = None
        logger.info("REST strategy server stopped")

    def _lookup(self, area_name: str) -> "RestExternalStrategy":
        strategy = self._strategies.get(area_name)
        if strategy is None:
            raise HTTPException(status_code=404, detail=f"Unknown area: {area_name!r}")
        return strategy

    def _build_app(self) -> FastAPI:
        app = FastAPI(
            title="ExternalStrategy REST API",
            description=(
                "Submit bids and offers to the running gsy-e simulation. "
                "Endpoints are namespaced by area name; inputs are applied at the "
                "start of the next market cycle."
            ),
        )

        @app.put("/{area_name}/bids", summary="Replace pending bid inputs")
        def put_bids(area_name: str, inputs: List[OrderInputRequest]) -> dict:
            return self._lookup(area_name).replace_pending_bids(inputs)

        @app.put("/{area_name}/offers", summary="Replace pending offer inputs")
        def put_offers(area_name: str, inputs: List[OrderInputRequest]) -> dict:
            return self._lookup(area_name).replace_pending_offers(inputs)

        @app.get("/{area_name}/bids", summary="Get current pending bid inputs")
        def get_bids(area_name: str) -> List[OrderInputRequest]:
            return self._lookup(area_name).snapshot_pending_bids()

        @app.get("/{area_name}/offers", summary="Get current pending offer inputs")
        def get_offers(area_name: str) -> List[OrderInputRequest]:
            return self._lookup(area_name).snapshot_pending_offers()

        return app


def configure_rest_server(
    host: str = DEFAULT_REST_HOST, port: int = DEFAULT_REST_PORT
) -> RestStrategyServer:
    """
    Configure the shared REST server's bind address before any strategies activate.

    Call this at simulation setup time. Once the server has started (i.e. at
    least one strategy has registered) the configuration is frozen and a fresh
    call raises ``RuntimeError``.
    """
    # pylint: disable=protected-access
    existing = RestStrategyServer._instance
    if existing is not None and existing._uvicorn_server is not None:
        raise RuntimeError("REST strategy server is already running; configure before activation.")
    RestStrategyServer._instance = RestStrategyServer(host=host, port=port)
    return RestStrategyServer._instance


class RestExternalStrategy(ExternalStrategyBase):
    """
    ExternalStrategyBase extended with REST access via the shared RestStrategyServer.

    On ``event_activate`` the strategy registers itself under ``self.area.name`` on
    the shared server. Requests to ``/{area.name}/bids`` and
    ``/{area.name}/offers`` are routed to this instance. At the start of every
    market cycle the pending inputs are flushed into the parent strategy.
    """

    def __init__(
        self,
        bid_inputs: Optional[List[ExternalOrderInput]] = None,
        offer_inputs: Optional[List[ExternalOrderInput]] = None,
    ) -> None:
        super().__init__(bid_inputs=bid_inputs, offer_inputs=offer_inputs)

        self._pending_lock = threading.Lock()
        self._pending_bid_inputs: List[ExternalOrderInput] = list(bid_inputs or [])
        self._pending_offer_inputs: List[ExternalOrderInput] = list(offer_inputs or [])

    def event_activate(self, **kwargs) -> None:
        super().event_activate(**kwargs)
        RestStrategyServer.instance().register(self.area.name, self)

    def event_market_cycle(self) -> None:
        """Flush pending REST inputs, then run the normal market-cycle logic."""
        with self._pending_lock:
            self.update_bid_inputs(list(self._pending_bid_inputs))
            self.update_offer_inputs(list(self._pending_offer_inputs))
        super().event_market_cycle()

    def event_deactivate(self) -> None:
        """Deregister from the shared server; the server stops when empty."""
        RestStrategyServer.instance().deregister(self.area.name)

    def replace_pending_bids(self, inputs: List[OrderInputRequest]) -> dict:
        """Replace the pending bid inputs from a REST request body."""
        parsed = [inp.to_external_order_input() for inp in inputs]
        with self._pending_lock:
            self._pending_bid_inputs = parsed
        return {"status": "ok", "count": len(parsed)}

    def replace_pending_offers(self, inputs: List[OrderInputRequest]) -> dict:
        """Replace the pending offer inputs from a REST request body."""
        parsed = [inp.to_external_order_input() for inp in inputs]
        with self._pending_lock:
            self._pending_offer_inputs = parsed
        return {"status": "ok", "count": len(parsed)}

    def snapshot_pending_bids(self) -> List[OrderInputRequest]:
        """Return the pending bid inputs as serialisable request objects."""
        with self._pending_lock:
            return [
                OrderInputRequest.from_external_order_input(inp)
                for inp in self._pending_bid_inputs
            ]

    def snapshot_pending_offers(self) -> List[OrderInputRequest]:
        """Return the pending offer inputs as serialisable request objects."""
        with self._pending_lock:
            return [
                OrderInputRequest.from_external_order_input(inp)
                for inp in self._pending_offer_inputs
            ]
