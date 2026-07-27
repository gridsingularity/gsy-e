from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Union, TYPE_CHECKING

from gsy_framework.constants_limits import FLOATING_POINT_TOLERANCE
from gsy_framework.data_classes import Trade, TraderDetails
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.utils import convert_pendulum_to_str_in_dict
from pendulum import DateTime, duration

from gsy_e.gsy_e_core.exceptions import BidNotFoundException, OfferNotFoundException
from gsy_e.models.strategy.order_updater import OrderUpdaterParameters, OrderUpdater
from gsy_e.models.strategy.state.smart_meter_state import SmartMeterState
from gsy_e.models.strategy.trading_strategy_base import TradingStrategyBase

if TYPE_CHECKING:
    from gsy_e.models.market import MarketBase


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


EXTERNAL_STRATEGY_MIN_PRICE = 0
EXTERNAL_STRATEGY_MAX_PRICE = 50


@dataclass
class ExternalOrderUpdaterParameters(OrderUpdaterParameters):
    """Order updater parameters for the external strategy."""

    update_interval: Optional[duration] = None
    initial_rate: Optional[Union[dict[DateTime, float], float, int]] = None
    final_rate: Optional[Union[dict[DateTime, float], float, int]] = None

    @staticmethod
    def _get_default_value_initial_rate(_):
        return EXTERNAL_STRATEGY_MIN_PRICE

    def _get_default_value_final_rate(self, _):
        return EXTERNAL_STRATEGY_MAX_PRICE

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


class LocalMarketOrderDispatcher:
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
        """Post a bid to the selected market."""
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
        order_id: str,
    ) -> None:
        """Delete a bid from a selected market."""
        market.delete_bid(order_id)

    def post_offer(
        self,
        market: "MarketBase",
        market_slot: DateTime,
        energy_kWh: float,
        rate: Decimal,
    ) -> Optional[str]:
        """Post an offer to a selected market."""
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
        order_id: str,
    ) -> None:
        """Delete an offer from a selected market."""
        market.delete_offer(order_id)


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
    ):
        super().__init__(
            order_updater_parameters={AvailableMarketTypes.SPOT: ExternalOrderUpdaterParameters()}
        )
        self._bid_inputs: List[ExternalOrderInput] = bid_inputs or []
        self._offer_inputs: List[ExternalOrderInput] = offer_inputs or []
        # LocalMarketOrderDispatcher construction is deferred to event_activate so
        # that it is initialised with the correct owner name/UUID.
        self._dispatcher = None
        self._slot_states: Dict[DateTime, ExternalOrderSlotState] = {}
        self._state = SmartMeterState()

    def update_bid_inputs(self, bid_inputs: List[ExternalOrderInput]) -> None:
        """Replace the list of bid inputs. Call this before the market cycle to update bids."""
        self._bid_inputs = bid_inputs

    def update_offer_inputs(self, offer_inputs: List[ExternalOrderInput]) -> None:
        """Replace the list of offer inputs. Call this before the market cycle to update offers."""
        self._offer_inputs = offer_inputs

    # pylint: disable=no-member
    def event_activate(self, **kwargs) -> None:
        """Create the default dispatcher once the owner area is known."""
        if self._dispatcher is None:
            self._dispatcher = LocalMarketOrderDispatcher(
                owner_name=self.owner.name,
                owner_uuid=self.owner.uuid,
            )

    def event_market_cycle(self) -> None:
        super().event_market_cycle()  # cleans up _order_updaters (no-op here)
        self._state.delete_past_state_values(self.area.now)
        self._clean_past_slot_states()
        spot_market = self.area.spot_market
        if spot_market is None:
            return
        self._open_slot(spot_market)

    def event_tick(self) -> None:
        self._update_open_orders()

    def event_bid_traded(self, *, market_id: str, bid_trade: Trade) -> None:
        """Decrement the energy requirement after a bid is matched."""
        if bid_trade.buyer.name != self.owner.name:
            return
        market = self.area.get_spot_or_future_market_by_id(market_id)
        if market is None:
            return
        self._state.decrement_energy_requirement(
            purchased_energy_Wh=bid_trade.traded_energy * 1000,
            time_slot=market.time_slot,
            area_name=self.owner.name,
        )

    def event_offer_traded(self, *, market_id: str, trade: Trade) -> None:
        """Decrement the available energy after an offer is matched."""
        if trade.seller.name != self.owner.name:
            return
        market = self.area.get_spot_or_future_market_by_id(market_id)
        if market is None:
            return
        self._state.decrement_available_energy(
            sold_energy_kWh=trade.traded_energy,
            time_slot=market.time_slot,
            area_name=self.owner.name,
        )

    # pylint: disable=too-many-locals
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

        # Scale each input's energy proportionally to the remaining state budget so that
        # re-posts after a price update never re-offer energy that has already been traded.
        total_bid_input_kWh = sum(inp.energy_kWh for inp in self._bid_inputs)
        total_bid_remaining_kWh = self._state.get_energy_requirement_Wh(market_slot, 0.0) / 1000

        total_offer_input_kWh = sum(inp.energy_kWh for inp in self._offer_inputs)
        total_offer_remaining_kWh = self._state.get_available_energy_kWh(market_slot, 0.0)

        for i, (bid_updater, bid_input) in enumerate(zip(state.bid_updaters, self._bid_inputs)):
            if total_bid_input_kWh > FLOATING_POINT_TOLERANCE:
                energy = bid_input.energy_kWh * total_bid_remaining_kWh / total_bid_input_kWh
            else:
                energy = 0.0
            rate = Decimal(str(order_rate)) if order_rate else bid_updater.get_energy_rate(now)
            state.open_bid_ids[i] = self._dispatcher.post_bid(market, market_slot, energy, rate)

        for i, (offer_updater, offer_input) in enumerate(
            zip(state.offer_updaters, self._offer_inputs)
        ):
            if total_offer_input_kWh > FLOATING_POINT_TOLERANCE:
                energy = offer_input.energy_kWh * total_offer_remaining_kWh / total_offer_input_kWh
            else:
                energy = 0.0
            rate = Decimal(str(order_rate)) if order_rate else offer_updater.get_energy_rate(now)
            state.open_offer_ids[i] = self._dispatcher.post_offer(
                market, market_slot, energy, rate
            )

    def remove_open_orders(self, market: "MarketBase", market_slot: DateTime) -> None:
        state = self._slot_states.get(market_slot)
        if state is None:
            return
        for i, bid_id in enumerate(state.open_bid_ids):
            if bid_id is not None:
                try:
                    self._dispatcher.delete_bid(market, bid_id)
                except BidNotFoundException:
                    pass
                state.open_bid_ids[i] = None
        for i, offer_id in enumerate(state.open_offer_ids):
            if offer_id is not None:
                try:
                    self._dispatcher.delete_offer(market, offer_id)
                except OfferNotFoundException:
                    pass
                state.open_offer_ids[i] = None

    def remove_order(self, market: "MarketBase", market_slot: DateTime, order_uuid: str) -> None:
        state = self._slot_states.get(market_slot)
        if state is None:
            return
        for i, bid_id in enumerate(state.open_bid_ids):
            if bid_id == order_uuid:
                self._dispatcher.delete_bid(market, order_uuid)
                state.open_bid_ids[i] = None
                return
        for i, offer_id in enumerate(state.open_offer_ids):
            if offer_id == order_uuid:
                self._dispatcher.delete_offer(market, order_uuid)
                state.open_offer_ids[i] = None
                return

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

        # Initialise the SmartMeterState budget for this slot before posting so that post_order
        # can use state values as the source of truth for remaining energy.
        if self._bid_inputs:
            total_bid_energy_Wh = sum(inp.energy_kWh for inp in self._bid_inputs) * 1000
            self._state.set_desired_energy(total_bid_energy_Wh, market_slot, overwrite=True)
        if self._offer_inputs:
            total_offer_energy_kWh = sum(inp.energy_kWh for inp in self._offer_inputs)
            self._state.set_available_energy(total_offer_energy_kWh, market_slot, overwrite=True)

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

    def serialize(self) -> Dict:
        return self._order_updater_params[AvailableMarketTypes.SPOT].serialize()

    @property
    def state(self) -> SmartMeterState:
        return self._state
