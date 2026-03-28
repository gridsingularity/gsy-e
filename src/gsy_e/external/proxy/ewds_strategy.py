"""
HTTP external strategy: a standalone trading strategy that manages bids and
offers exclusively through HTTP.

This module has **no dependency on gsy-e internals**.  It can be deployed
independently or embedded inside a gsy-e process without coupling to the
simulation engine.

Intended usage
--------------
1. Subclass :class:`EWDSConnection` and implement each stub method with
   the real HTTP calls once the API endpoints are finalised.
2. Instantiate :class:`HttpExternalStrategy` with your connector, bid inputs,
   and offer inputs.
3. Call :meth:`~HttpExternalStrategy.on_market_cycle` once per market cycle
   and :meth:`~HttpExternalStrategy.on_tick` on every tick.
4. Forward trade notifications via
   :meth:`~HttpExternalStrategy.on_bid_traded` /
   :meth:`~HttpExternalStrategy.on_offer_traded` so that the remaining energy
   budget stays accurate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from pendulum import DateTime, Duration, duration

from gsy_e.external.proxy.connection import EWDSConnection, EWDSMarketSlotInfo
from gsy_e.external.proxy.price_updater import SlotPriceUpdater


logger = logging.getLogger(__name__)


_DEFAULT_UPDATE_INTERVAL: Duration = duration(minutes=5)
EPSILON: float = 1e-5


@dataclass
class HttpOrderInput:
    """
    Caller-supplied parameters for a bid or offer over one market slot.

    Attributes:
        energy_kWh: Volume to trade.
        min_price: Lower bound of the price range.
            For bids this is the *opening* (initial) rate.
            For offers this is the *closing* (final) rate.
        max_price: Upper bound of the price range.
            For bids this is the *closing* (final) rate.
            For offers this is the *opening* (initial) rate.
        time_slot: Optional nominal delivery slot (informational only; the
            actual slot is determined by the market).
    """

    energy_kWh: float
    min_price: float
    max_price: float
    time_slot: Optional[DateTime] = None


@dataclass
class _HttpSlotState:
    """Tracks open orders and price updaters for a single market slot."""

    slot_info: EWDSMarketSlotInfo
    bid_updaters: List[SlotPriceUpdater] = field(default_factory=list)
    offer_updaters: List[SlotPriceUpdater] = field(default_factory=list)
    open_bid_ids: List[Optional[str]] = field(default_factory=list)
    open_offer_ids: List[Optional[str]] = field(default_factory=list)
    remaining_bid_energy_kWh: float = 0.0
    remaining_offer_energy_kWh: float = 0.0


class EWDSExternalStrategy:
    """
    Standalone trading strategy that manages bids and offers via Energy Web Digital Spine.

    Unlike ``ExternalStrategyBase`` this class has **no dependency on gsy-e**
    internals.  It is driven entirely by external calls:

    * :meth:`on_market_cycle` — call once per market cycle.  Fetches active
      slots from the connector, initialises :class:`SlotPriceUpdater` instances
      for each new slot, and posts initial orders.
    * :meth:`on_tick` — call on every simulation tick or polling interval.
      Updates prices when the :class:`SlotPriceUpdater` decides it is time to
      do so.
    * :meth:`on_bid_traded` / :meth:`on_offer_traded` — call whenever the
      exchange notifies you that one of your orders was matched.  This keeps
      the remaining energy budget accurate so that subsequent re-posts never
      exceed the already-traded volume.

    Parameters
    ----------
    connector:
        An :class:`EWDSConnection` instance.  Pass a
        :class:`StubEWDSConnection` (or a :class:`unittest.mock.MagicMock`)
        during development.
    bid_inputs:
        Bids to post on each new market slot.
    offer_inputs:
        Offers to post on each new market slot.
    update_interval:
        How often prices are updated within a slot.  Defaults to 5 minutes.
    """

    def __init__(
        self,
        connector: EWDSConnection,
        bid_inputs: Optional[List[HttpOrderInput]] = None,
        offer_inputs: Optional[List[HttpOrderInput]] = None,
        update_interval: Optional[Duration] = None,
    ) -> None:
        self._connector = connector
        self._bid_inputs: List[HttpOrderInput] = bid_inputs or []
        self._offer_inputs: List[HttpOrderInput] = offer_inputs or []
        self._update_interval: Duration = update_interval or _DEFAULT_UPDATE_INTERVAL
        self._slot_states: Dict[DateTime, _HttpSlotState] = {}

    def update_bid_inputs(self, bid_inputs: List[HttpOrderInput]) -> None:
        """Replace the bid input list before the next market cycle."""
        self._bid_inputs = bid_inputs

    def update_offer_inputs(self, offer_inputs: List[HttpOrderInput]) -> None:
        """Replace the offer input list before the next market cycle."""
        self._offer_inputs = offer_inputs

    def on_market_cycle(self, now: DateTime) -> None:
        """
        Open new market slots and post initial orders.

        Call this once per market cycle, passing the current wall-clock time.
        Expired slots are cleaned up first; then active slots are fetched from
        the connector and any slot not yet tracked is initialised.
        """
        self._clean_expired_slots(now)
        for slot_info in self._connector.get_active_market_slots():
            self._open_slot(slot_info, now)

    def on_tick(self, now: DateTime) -> None:
        """
        Update order prices for all open slots if a price update is due.

        Call this on every simulation tick or polling interval.
        """
        for slot, state in list(self._slot_states.items()):
            bid_due = any(u.is_time_for_update(now) for u in state.bid_updaters)
            offer_due = any(u.is_time_for_update(now) for u in state.offer_updaters)
            if bid_due or offer_due:
                self._cancel_open_orders(slot, state)
                self._post_orders(slot, state, now)

    def on_bid_traded(self, slot: DateTime, traded_energy_kWh: float) -> None:
        """
        Reduce the remaining bid energy for ``slot`` by ``traded_energy_kWh``.

        Call this when the exchange confirms that one of your bids was matched.
        """
        state = self._slot_states.get(slot)
        if state is None:
            return
        state.remaining_bid_energy_kWh = max(
            0.0, state.remaining_bid_energy_kWh - traded_energy_kWh
        )

    def on_offer_traded(self, slot: DateTime, traded_energy_kWh: float) -> None:
        """
        Reduce the remaining offer energy for ``slot`` by ``traded_energy_kWh``.

        Call this when the exchange confirms that one of your offers was matched.
        """
        state = self._slot_states.get(slot)
        if state is None:
            return
        state.remaining_offer_energy_kWh = max(
            0.0, state.remaining_offer_energy_kWh - traded_energy_kWh
        )

    def _open_slot(self, slot_info: EWDSMarketSlotInfo, now: DateTime) -> None:
        slot = slot_info.opening_time
        if slot in self._slot_states:
            return

        state = _HttpSlotState(
            slot_info=slot_info,
            remaining_bid_energy_kWh=sum(i.energy_kWh for i in self._bid_inputs),
            remaining_offer_energy_kWh=sum(i.energy_kWh for i in self._offer_inputs),
        )

        for bid_input in self._bid_inputs:
            state.bid_updaters.append(
                SlotPriceUpdater(
                    initial_rate=Decimal(str(bid_input.min_price)),
                    final_rate=Decimal(str(bid_input.max_price)),
                    opening_time=slot_info.opening_time,
                    closing_time=slot_info.closing_time,
                    update_interval=self._update_interval,
                )
            )
            state.open_bid_ids.append(None)

        for offer_input in self._offer_inputs:
            state.offer_updaters.append(
                SlotPriceUpdater(
                    initial_rate=Decimal(str(offer_input.max_price)),
                    final_rate=Decimal(str(offer_input.min_price)),
                    opening_time=slot_info.opening_time,
                    closing_time=slot_info.closing_time,
                    update_interval=self._update_interval,
                )
            )
            state.open_offer_ids.append(None)

        self._slot_states[slot] = state
        self._post_orders(slot, state, now)

    def _post_orders(self, slot: DateTime, state: _HttpSlotState, now: DateTime) -> None:
        total_bid_input = sum(i.energy_kWh for i in self._bid_inputs)
        total_offer_input = sum(i.energy_kWh for i in self._offer_inputs)
        market_id = state.slot_info.market_id
        time_slot = state.slot_info.delivery_start_time

        for i, (updater, inp) in enumerate(zip(state.bid_updaters, self._bid_inputs)):
            if total_bid_input > EPSILON:
                energy = inp.energy_kWh * state.remaining_bid_energy_kWh / total_bid_input
            else:
                energy = 0.0
            rate = updater.get_rate(now)
            state.open_bid_ids[i] = self._connector.post_bid(market_id, time_slot, energy, rate)

        for i, (updater, inp) in enumerate(zip(state.offer_updaters, self._offer_inputs)):
            if total_offer_input > EPSILON:
                energy = inp.energy_kWh * state.remaining_offer_energy_kWh / total_offer_input
            else:
                energy = 0.0
            rate = updater.get_rate(now)
            state.open_offer_ids[i] = self._connector.post_offer(
                market_id, time_slot, energy, rate
            )

    def _cancel_open_orders(self, slot: DateTime, state: _HttpSlotState) -> None:
        for i, bid_id in enumerate(state.open_bid_ids):
            if bid_id is not None:
                try:
                    self._connector.delete_bid(slot, bid_id)
                except Exception:  # pylint: disable=broad-except
                    logger.warning("Failed to delete bid %s for slot %s", bid_id, slot)
                state.open_bid_ids[i] = None

        for i, offer_id in enumerate(state.open_offer_ids):
            if offer_id is not None:
                try:
                    self._connector.delete_offer(slot, offer_id)
                except Exception:  # pylint: disable=broad-except
                    logger.warning("Failed to delete offer %s for slot %s", offer_id, slot)
                state.open_offer_ids[i] = None

    def _clean_expired_slots(self, now: DateTime) -> None:
        expired = [
            slot
            for slot, state in self._slot_states.items()
            if state.slot_info.closing_time <= now
        ]
        for slot in expired:
            del self._slot_states[slot]
