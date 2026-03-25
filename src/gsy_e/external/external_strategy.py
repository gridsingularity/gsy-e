from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import auto, Enum
from typing import Dict, List, Optional, Union, TYPE_CHECKING

from gsy_framework.constants_limits import FLOATING_POINT_TOLERANCE
from gsy_framework.data_classes import Trade, TraderDetails
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.utils import convert_pendulum_to_str_in_dict
from pendulum import DateTime, duration

from gsy_e.models.strategy.order_updater import OrderUpdaterParameters, OrderUpdater
from gsy_e.models.strategy.trading_strategy_base import TradingStrategyBase

if TYPE_CHECKING:
    from gsy_e.models.market import MarketBase


COMMUNITY_MIN_PRICE = 10
COMMUNITY_MAX_PRICE = 50


class OrderDispatchMode(Enum):
    """Determines how bid/offer orders are dispatched."""

    HTTP = auto()
    LOCAL_MARKET = auto()


@dataclass
class ExternalOrderInput:
    """
    Input parameters provided by the caller for a bid or offer to be managed
    over a single market slot.

    Attributes:
        energy_kWh: Amount of energy to bid or offer.
        min_price: Lower bound of the price range (initial bid rate / final offer rate).
        max_price: Upper bound of the price range (final bid rate / initial offer rate).
        market_type: Which market the order targets.
        time_slot: The delivery time slot for the order.
    """

    energy_kWh: float
    min_price: float
    max_price: float
    market_type: AvailableMarketTypes
    time_slot: DateTime


@dataclass
class ExternalOrderUpdaterParameters(OrderUpdaterParameters):
    """Order updater parameters for the external strategy."""

    update_interval: Optional[duration] = None
    initial_rate: Optional[Union[dict[DateTime, float], float, int]] = None
    final_rate: Optional[Union[dict[DateTime, float], float, int]] = None

    @staticmethod
    def _get_default_value_initial_rate(_):
        return COMMUNITY_MIN_PRICE

    def _get_default_value_final_rate(self, _):
        return COMMUNITY_MAX_PRICE

    def serialize(self):
        return {
            "update_interval": self.update_interval,
            "initial_rate": (
                self.initial_rate
                if isinstance(self.initial_rate, (type(None), int, float))
                else convert_pendulum_to_str_in_dict(self.initial_rate)
            ),
            "final_rate": (
                self.final_rate
                if isinstance(self.final_rate, (type(None), int, float))
                else convert_pendulum_to_str_in_dict(self.final_rate)
            ),
        }


@dataclass
class ExternalOrderSlotState:
    """Tracks active OrderUpdaters and open order IDs for a single market slot.

    Each list is parallel to the bid/offer inputs: index *i* in ``bid_updaters``
    corresponds to index *i* in ``open_bid_ids``, and likewise for offers.
    """

    bid_updaters: List[OrderUpdater] = field(default_factory=list)
    offer_updaters: List[OrderUpdater] = field(default_factory=list)
    open_bid_ids: List[Optional[str]] = field(default_factory=list)
    open_offer_ids: List[Optional[str]] = field(default_factory=list)
    closing_time: Optional[DateTime] = None


class OrderDispatcherBase(ABC):
    """
    ABC for order dispatching.

    Concrete implementations either route orders to an HTTP service or place them
    directly in a gsy-e market object. The active implementation is chosen via
    ``OrderDispatchMode`` and can be swapped at construction time of
    ``ExternalStrategyBase``.
    """

    @abstractmethod
    def post_bid(
        self,
        market: "MarketBase",
        market_slot: DateTime,
        energy_kWh: float,
        rate: Decimal,
    ) -> Optional[str]:
        """Post a bid. Returns the order ID, or None if the order was not placed."""

    @abstractmethod
    def delete_bid(
        self,
        market: "MarketBase",
        market_slot: DateTime,
        order_id: str,
    ) -> None:
        """Delete a bid by order ID."""

    @abstractmethod
    def post_offer(
        self,
        market: "MarketBase",
        market_slot: DateTime,
        energy_kWh: float,
        rate: Decimal,
    ) -> Optional[str]:
        """Post an offer. Returns the order ID, or None if the order was not placed."""

    @abstractmethod
    def delete_offer(
        self,
        market: "MarketBase",
        market_slot: DateTime,
        order_id: str,
    ) -> None:
        """Delete an offer by order ID."""


class HttpOrderDispatcher(OrderDispatcherBase):
    """
    Routes orders to an external service via HTTP.

    All method bodies are stubs pending definition of the external HTTP interface.
    """

    def post_bid(
        self,
        market: "MarketBase",
        market_slot: DateTime,
        energy_kWh: float,
        rate: Decimal,
    ) -> Optional[str]:
        """Send HTTP request to post a bid. To be implemented."""

    def delete_bid(
        self,
        market: "MarketBase",
        market_slot: DateTime,
        order_id: str,
    ) -> None:
        """Send HTTP request to delete a bid. To be implemented."""

    def post_offer(
        self,
        market: "MarketBase",
        market_slot: DateTime,
        energy_kWh: float,
        rate: Decimal,
    ) -> Optional[str]:
        """Send HTTP request to post an offer. To be implemented."""

    def delete_offer(
        self,
        market: "MarketBase",
        market_slot: DateTime,
        order_id: str,
    ) -> None:
        """Send HTTP request to delete an offer. To be implemented."""


class LocalMarketOrderDispatcher(OrderDispatcherBase):
    """Places orders directly into a gsy-e market object."""

    def __init__(self, owner_name: str, owner_uuid: str):
        self._owner = TraderDetails(owner_name, owner_uuid, owner_name, owner_uuid)

    def post_bid(
        self,
        market: "MarketBase",
        market_slot: DateTime,
        energy_kWh: float,
        rate: Decimal,
    ) -> Optional[str]:
        if energy_kWh <= FLOATING_POINT_TOLERANCE:
            return None
        price = float(rate * Decimal(str(energy_kWh)))
        bid = market.bid(
            price=price,
            energy=energy_kWh,
            buyer=self._owner,
            original_price=price,
            time_slot=market_slot,
        )
        return bid.id

    def delete_bid(
        self,
        market: "MarketBase",
        market_slot: DateTime,
        order_id: str,
    ) -> None:
        market.delete_bid(order_id)

    def post_offer(
        self,
        market: "MarketBase",
        market_slot: DateTime,
        energy_kWh: float,
        rate: Decimal,
    ) -> Optional[str]:
        if energy_kWh <= FLOATING_POINT_TOLERANCE:
            return None
        price = float(rate * Decimal(str(energy_kWh)))
        offer = market.offer(
            price=price,
            energy=energy_kWh,
            seller=self._owner,
            original_price=price,
            time_slot=market_slot,
        )
        return offer.id

    def delete_offer(
        self,
        market: "MarketBase",
        market_slot: DateTime,
        order_id: str,
    ) -> None:
        market.delete_offer(order_id)


def create_order_dispatcher(
    mode: OrderDispatchMode,
    owner_name: str = "AssetOwner",
    owner_uuid: str = "",
) -> OrderDispatcherBase:
    """Factory: returns the appropriate ``OrderDispatcherBase`` for the given mode."""
    if mode == OrderDispatchMode.HTTP:
        return HttpOrderDispatcher()
    if mode == OrderDispatchMode.LOCAL_MARKET:
        return LocalMarketOrderDispatcher(owner_name, owner_uuid)
    raise ValueError(f"Unsupported OrderDispatchMode: {mode}")


class ExternalStrategyBase(TradingStrategyBase):
    """
    Trading strategy for an externally-managed asset.

    Accepts bid and/or offer inputs containing energy amounts and min/max prices.
    An ``OrderUpdater`` linearly interpolates the price across each market slot:

    * **Bids**: price starts at ``min_price`` and rises toward ``max_price``.
    * **Offers**: price starts at ``max_price`` and falls toward ``min_price``.

    On every price update the active ``OrderDispatcherBase`` implementation either
    sends HTTP requests or writes directly to the gsy-e market – swappable via
    ``OrderDispatchMode`` (or by injecting a custom dispatcher instance).
    """

    def __init__(
        self,
        bid_inputs: Optional[List[ExternalOrderInput]] = None,
        offer_inputs: Optional[List[ExternalOrderInput]] = None,
        dispatcher: Optional[OrderDispatcherBase] = None,
        dispatch_mode: OrderDispatchMode = OrderDispatchMode.LOCAL_MARKET,
    ):
        super().__init__(
            order_updater_parameters={AvailableMarketTypes.SPOT: ExternalOrderUpdaterParameters()}
        )
        self._bid_inputs: List[ExternalOrderInput] = bid_inputs or []
        self._offer_inputs: List[ExternalOrderInput] = offer_inputs or []
        self._dispatcher: OrderDispatcherBase = dispatcher or create_order_dispatcher(
            dispatch_mode
        )
        self._slot_states: Dict[DateTime, ExternalOrderSlotState] = {}

    # ------------------------------------------------------------------
    # Input update helpers (called by the external owner before each cycle)
    # ------------------------------------------------------------------

    def update_bid_inputs(self, bid_inputs: List[ExternalOrderInput]) -> None:
        """Replace the list of bid inputs. Call this before the market cycle to update bids."""
        self._bid_inputs = bid_inputs

    def update_offer_inputs(self, offer_inputs: List[ExternalOrderInput]) -> None:
        """Replace the list of offer inputs. Call this before the market cycle to update offers."""
        self._offer_inputs = offer_inputs

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    # pylint: disable=no-member
    def event_market_cycle(self) -> None:
        super().event_market_cycle()  # cleans up _order_updaters (no-op here)
        self._clean_past_slot_states()
        spot_market = self.area.spot_market
        if spot_market is None:
            return
        self._open_slot(spot_market)

    def event_tick(self) -> None:
        self._update_open_orders()

    def event_bid_traded(self, *, market_id: str, bid_trade: Trade) -> None:
        """Handle a bid trade. Override in subclasses to update energy accounting."""

    def event_offer_traded(self, *, market_id: str, trade: Trade) -> None:
        """Handle an offer trade. Override in subclasses to update energy accounting."""

    # ------------------------------------------------------------------
    # TradingStrategyBase abstract method implementations
    # ------------------------------------------------------------------

    def post_order(
        self,
        market: "MarketBase",
        market_slot: DateTime,
        order_rate: float = None,
        **kwargs,
    ) -> None:
        state = self._slot_states.get(market_slot)
        if state is None:
            return
        now = self.area.now  # pylint: disable=no-member

        for i, (bid_updater, bid_input) in enumerate(zip(state.bid_updaters, self._bid_inputs)):
            rate = Decimal(str(order_rate)) if order_rate else bid_updater.get_energy_rate(now)
            state.open_bid_ids[i] = self._dispatcher.post_bid(
                market, market_slot, bid_input.energy_kWh, rate
            )

        for i, (offer_updater, offer_input) in enumerate(
            zip(state.offer_updaters, self._offer_inputs)
        ):
            rate = Decimal(str(order_rate)) if order_rate else offer_updater.get_energy_rate(now)
            state.open_offer_ids[i] = self._dispatcher.post_offer(
                market, market_slot, offer_input.energy_kWh, rate
            )

    def remove_open_orders(self, market: "MarketBase", market_slot: DateTime) -> None:
        state = self._slot_states.get(market_slot)
        if state is None:
            return
        for i, bid_id in enumerate(state.open_bid_ids):
            if bid_id is not None:
                self._dispatcher.delete_bid(market, market_slot, bid_id)
                state.open_bid_ids[i] = None
        for i, offer_id in enumerate(state.open_offer_ids):
            if offer_id is not None:
                self._dispatcher.delete_offer(market, market_slot, offer_id)
                state.open_offer_ids[i] = None

    def remove_order(self, market: "MarketBase", market_slot: DateTime, order_uuid: str) -> None:
        state = self._slot_states.get(market_slot)
        if state is None:
            return
        for i, bid_id in enumerate(state.open_bid_ids):
            if bid_id == order_uuid:
                self._dispatcher.delete_bid(market, market_slot, order_uuid)
                state.open_bid_ids[i] = None
                return
        for i, offer_id in enumerate(state.open_offer_ids):
            if offer_id == order_uuid:
                self._dispatcher.delete_offer(market, market_slot, order_uuid)
                state.open_offer_ids[i] = None
                return

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_slot(self, spot_market: "MarketBase") -> None:
        """Create slot state and post initial orders for a newly opened market slot."""
        market_slot = spot_market.time_slot
        if market_slot in self._slot_states:
            return

        market_params = spot_market.get_market_parameters_for_market_slot(market_slot)
        state = ExternalOrderSlotState(
            closing_time=market_params.closing_time if market_params else None,
        )

        if market_params is not None:
            for bid_input in self._bid_inputs:
                state.bid_updaters.append(
                    OrderUpdater(
                        ExternalOrderUpdaterParameters(
                            initial_rate=bid_input.min_price,
                            final_rate=bid_input.max_price,
                        ),
                        market_params,
                    )
                )
                state.open_bid_ids.append(None)

            for offer_input in self._offer_inputs:
                state.offer_updaters.append(
                    OrderUpdater(
                        ExternalOrderUpdaterParameters(
                            initial_rate=offer_input.max_price,
                            final_rate=offer_input.min_price,
                        ),
                        market_params,
                    )
                )
                state.open_offer_ids.append(None)

        self._slot_states[market_slot] = state
        self.post_order(spot_market, market_slot)

    def _update_open_orders(self) -> None:
        spot_market = self.area.spot_market  # pylint: disable=no-member
        if spot_market is None:
            return
        market_slot = spot_market.time_slot
        state = self._slot_states.get(market_slot)
        if state is None:
            return

        now = self.area.now  # pylint: disable=no-member
        bid_due = any(u.is_time_for_update(now) for u in state.bid_updaters)
        offer_due = any(u.is_time_for_update(now) for u in state.offer_updaters)
        if bid_due or offer_due:
            self.remove_open_orders(spot_market, market_slot)
            self.post_order(spot_market, market_slot)

    def _clean_past_slot_states(self) -> None:
        now = self.area.now  # pylint: disable=no-member
        expired = [
            slot
            for slot, state in self._slot_states.items()
            if state.closing_time is not None and state.closing_time <= now
        ]
        for slot in expired:
            del self._slot_states[slot]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def serialize(self) -> Dict:
        return self._order_updater_params[AvailableMarketTypes.SPOT].serialize()

    @property
    def state(self):
        return None
