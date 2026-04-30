"""
Energy Web Client Gateway: a standalone trading strategy that manages bids and offers exclusively
through via the Client Gateway.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional, Callable

from pendulum import DateTime, Duration, duration, now

from gsy_e.external.proxy.dataclasses import (
    MarketSlotInfo,
    EnergyTrade,
    MarketType,
)
from gsy_e.external.proxy.ewcg_connection import EWClientGatewayConnection
from gsy_e.external.proxy.price_updater import SlotPriceUpdater

logger = logging.getLogger(__name__)


_DEFAULT_UPDATE_INTERVAL: Duration = duration(minutes=5)
EPSILON: float = 1e-5
TIMEZONE: str = "UTC"


@dataclass
class OrderInput:
    """
    Bid or offer parameters over one market slot. Caller of the class should provide them.
    """

    energy_kWh: float
    min_price: float
    max_price: float
    time_slot: Optional[DateTime] = None
    market_type: MarketType = MarketType.SPOT


@dataclass
class MarketSlotState:
    """Tracks open orders and price updaters for a single market slot."""

    slot_info: MarketSlotInfo
    bid_updaters: List[SlotPriceUpdater] = field(default_factory=list)
    offer_updaters: List[SlotPriceUpdater] = field(default_factory=list)
    remaining_bid_energy_kWh: float = 0.0
    remaining_offer_energy_kWh: float = 0.0

    @property
    def open_bid_ids(self):
        """Lists ids of all open bids."""
        return [updater.order_id for updater in self.bid_updaters]

    @property
    def open_offer_ids(self):
        """List ids of all open offers."""
        return [updater.order_id for updater in self.offer_updaters]


class EWCGExternalStrategy:
    """
    Standalone trading strategy that manages bids and offers via Energy Web Client Gateway.

    This class has no dependency on gsy-e internals.  It is driven entirely by callback methods:
    * on_market_cycle: call once per market cycle.  Fetches active slots from the connector,
      initialises :class:`SlotPriceUpdater` instances for each new slot, and posts initial orders.
    * on_tick: call on every tick or polling interval. Updates prices when the SlotPriceUpdater
      decides it is time to do so.
    * on_order_traded: call whenever the exchange notifies you that one of your orders was matched.
      This keeps the remaining energy budget accurate so that following order updates never exceed
      the already-traded volume.
    """

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        connector: EWClientGatewayConnection,
        bid_inputs: Optional[List[OrderInput]] = None,
        offer_inputs: Optional[List[OrderInput]] = None,
        update_interval: Optional[Duration] = None,
        trade_callback: Optional[Callable[[EnergyTrade], None]] = None,
        new_market_callback: Optional[Callable[[MarketSlotInfo], None]] = None,
    ) -> None:
        self._connector = connector
        self._bid_inputs: List[OrderInput] = bid_inputs or []
        self._offer_inputs: List[OrderInput] = offer_inputs or []
        self._update_interval: Duration = update_interval or _DEFAULT_UPDATE_INTERVAL
        self._slot_states: List[MarketSlotState] = []
        self._trade_callback = trade_callback
        self._new_market_callback = new_market_callback
        self._connector.subscribe(
            on_market_slot=self.on_market_slot, on_trade=self.on_order_traded
        )

    def update_bid_inputs(self, bid_inputs: List[OrderInput]) -> None:
        """Replace the bid input list before the next market cycle."""
        self._bid_inputs = bid_inputs

    def update_offer_inputs(self, offer_inputs: List[OrderInput]) -> None:
        """Replace the offer input list before the next market cycle."""
        self._offer_inputs = offer_inputs

    @property
    def now(self) -> DateTime:
        """Return the current time."""
        return now(TIMEZONE)

    def on_market_slot(self, market_slot_info: MarketSlotInfo) -> None:
        """
        Open new market slots and post initial orders. Expired slots are cleaned up first; then
        active slots are fetched from the connector, and any slot not yet tracked is initialised.
        """
        self._clean_expired_slots()
        self._open_slot(market_slot_info)
        if self._new_market_callback:
            self._new_market_callback(market_slot_info)

    def on_tick(self) -> None:
        """
        Update order prices for all open slots if a price update is due.

        Call this on every simulation tick or polling interval.
        """
        for state in self._slot_states:
            bid_due = any(u.is_time_for_update(self.now) for u in state.bid_updaters)
            offer_due = any(u.is_time_for_update(self.now) for u in state.offer_updaters)
            if bid_due or offer_due:
                self._cancel_open_orders(state)

                bids_for_slot = [
                    bid
                    for bid in self._bid_inputs
                    if bid.time_slot == state.slot_info.delivery_start_time
                    and bid.market_type == state.slot_info.market_type
                ]
                offers_for_slot = [
                    offer
                    for offer in self._offer_inputs
                    if offer.time_slot == state.slot_info.delivery_start_time
                    and offer.market_type == state.slot_info.market_type
                ]

                self._post_orders(state, bids_for_slot, offers_for_slot)

    def on_order_traded(self, trade: EnergyTrade) -> None:
        """
        Reduce the remaining bid energy for the market slot by traded_energy_kWh.
        Call this when the exchange confirms that an order was matched.
        """
        state = next(
            (s for s in self._slot_states if s.slot_info.market_id == trade.market_id), None
        )
        if state is None:
            return
        if trade.bid_id in state.open_bid_ids:
            state.remaining_bid_energy_kWh = max(
                0.0, state.remaining_bid_energy_kWh - trade.energy_kWh
            )
        if trade.offer_id in state.open_offer_ids:
            state.remaining_offer_energy_kWh = max(
                0.0, state.remaining_offer_energy_kWh - trade.energy_kWh
            )

        if self._trade_callback:
            self._trade_callback(trade)

    def _open_slot(self, market_slot_info: MarketSlotInfo) -> None:
        open_market_ids = [state.slot_info.market_id for state in self._slot_states]
        if market_slot_info.market_id in open_market_ids:
            return

        state = MarketSlotState(
            slot_info=market_slot_info,
            remaining_bid_energy_kWh=sum(i.energy_kWh for i in self._bid_inputs),
            remaining_offer_energy_kWh=sum(i.energy_kWh for i in self._offer_inputs),
        )

        bids_for_slot = [
            bid
            for bid in self._bid_inputs
            if bid.time_slot == state.slot_info.delivery_start_time
            and bid.market_type == state.slot_info.market_type
        ]
        offers_for_slot = [
            offer
            for offer in self._offer_inputs
            if offer.time_slot == state.slot_info.delivery_start_time
            and offer.market_type == state.slot_info.market_type
        ]

        for bid_input in bids_for_slot:
            state.bid_updaters.append(
                SlotPriceUpdater(
                    initial_rate=Decimal(str(bid_input.min_price)),
                    final_rate=Decimal(str(bid_input.max_price)),
                    opening_time=market_slot_info.opening_time,
                    closing_time=market_slot_info.closing_time,
                    update_interval=self._update_interval,
                )
            )
            state.open_bid_ids.append(None)

        for offer_input in offers_for_slot:
            state.offer_updaters.append(
                SlotPriceUpdater(
                    initial_rate=Decimal(str(offer_input.max_price)),
                    final_rate=Decimal(str(offer_input.min_price)),
                    opening_time=market_slot_info.opening_time,
                    closing_time=market_slot_info.closing_time,
                    update_interval=self._update_interval,
                )
            )
            state.open_offer_ids.append(None)

        self._slot_states.append(state)
        self._post_orders(state, bids_for_slot, offers_for_slot)

    def _post_orders(
        self,
        state: MarketSlotState,
        bids_for_slot: List[OrderInput],
        offers_for_slot: List[OrderInput],
    ) -> None:

        total_bid_input = sum(bid.energy_kWh for bid in bids_for_slot)
        total_offer_input = sum(offer.energy_kWh for offer in offers_for_slot)
        market_id = state.slot_info.market_id
        time_slot = state.slot_info.delivery_start_time

        for updater, inp in zip(state.bid_updaters, bids_for_slot):
            if total_bid_input > EPSILON:
                energy = inp.energy_kWh * state.remaining_bid_energy_kWh / total_bid_input
            else:
                energy = 0.0
            rate = updater.get_rate(self.now)
            updater.order_id = self._connector.post_bid(market_id, time_slot, energy, rate)

        for updater, inp in zip(state.offer_updaters, offers_for_slot):
            if total_offer_input > EPSILON:
                energy = inp.energy_kWh * state.remaining_offer_energy_kWh / total_offer_input
            else:
                energy = 0.0
            rate = updater.get_rate(self.now)
            updater.order_id = self._connector.post_offer(market_id, time_slot, energy, rate)

    def _cancel_open_orders(self, state: MarketSlotState) -> None:
        slot = state.slot_info.delivery_start_time
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

    def _clean_expired_slots(self) -> None:
        self._slot_states = [
            state for state in self._slot_states if state.slot_info.closing_time > self.now
        ]


def create_strategy(
    bid_inputs: Optional[List[OrderInput]] = None,
    offer_inputs: Optional[List[OrderInput]] = None,
    actor_id: str = "ewds_strategy",
    actor_type: str = "Prosumer",
    update_interval: Optional[Duration] = None,
) -> EWCGExternalStrategy:
    """Create a new EWCGExternalStrategy."""
    return EWCGExternalStrategy(
        EWClientGatewayConnection(actor_id, actor_type), bid_inputs, offer_inputs, update_interval
    )
