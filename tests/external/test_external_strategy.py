# pylint: disable=missing-function-docstring, protected-access, missing-class-docstring
"""Unit tests for ExternalStrategyBase in gsy_e.external.external_strategy."""
from decimal import Decimal
from unittest.mock import MagicMock

import pendulum
from gsy_framework.enums import AvailableMarketTypes

from gsy_e.models.market import MarketSlotParams
from gsy_e.external.external_strategy import (
    ExternalOrderInput,
    ExternalOrderSlotState,
    ExternalStrategyBase,
    LocalMarketOrderDispatcher,
    OrderUpdater,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SLOT_START = pendulum.datetime(2024, 1, 1, 12, 0, tz="UTC")
SLOT_END = SLOT_START.add(minutes=15)
DELIVERY_START = SLOT_END
DELIVERY_END = DELIVERY_START.add(minutes=15)

BID_ENERGY = 1.0
OFFER_ENERGY = 2.0
MIN_PRICE = 10.0
MAX_PRICE = 50.0


def make_market_slot_params(
    opening=SLOT_START, closing=SLOT_END, delivery_start=DELIVERY_START, delivery_end=DELIVERY_END
):
    return MarketSlotParams(
        opening_time=opening,
        closing_time=closing,
        delivery_start_time=delivery_start,
        delivery_end_time=delivery_end,
    )


def make_bid_input(
    energy=BID_ENERGY, min_price=MIN_PRICE, max_price=MAX_PRICE, time_slot=SLOT_START
):
    return ExternalOrderInput(
        energy_kWh=energy,
        min_price=min_price,
        max_price=max_price,
        market_type=AvailableMarketTypes.SPOT,
        time_slot=time_slot,
    )


def make_offer_input(
    energy=OFFER_ENERGY, min_price=MIN_PRICE, max_price=MAX_PRICE, time_slot=SLOT_START
):
    return ExternalOrderInput(
        energy_kWh=energy,
        min_price=min_price,
        max_price=max_price,
        market_type=AvailableMarketTypes.SPOT,
        time_slot=time_slot,
    )


def make_mock_market(time_slot=SLOT_START):
    """Return a market mock that behaves like a real market for order operations."""
    market = MagicMock()
    market.time_slot = time_slot
    market.get_market_parameters_for_market_slot.return_value = make_market_slot_params()

    bid_mock = MagicMock()
    bid_mock.id = "bid-id-001"
    market.bid.return_value = bid_mock

    offer_mock = MagicMock()
    offer_mock.id = "offer-id-001"
    market.offer.return_value = offer_mock

    return market


def make_strategy(bid_inputs=None, offer_inputs=None, dispatcher=None):
    """Build an ExternalStrategyBase with a mocked area and an optional mock dispatcher."""
    strategy = ExternalStrategyBase(
        bid_inputs=bid_inputs,
        offer_inputs=offer_inputs,
    )
    area_mock = MagicMock()
    area_mock.now = SLOT_START
    strategy.area = area_mock
    if dispatcher is not None:
        strategy._dispatcher = dispatcher
    return strategy


def make_slot_state_with_updaters(n_bids=1, n_offers=1):
    """Return an ExternalOrderSlotState pre-populated with mock updaters and None order IDs."""
    updater_mock = MagicMock(spec=OrderUpdater)
    updater_mock.get_energy_rate.return_value = Decimal("20")
    updater_mock.is_time_for_update.return_value = False
    return ExternalOrderSlotState(
        bid_updaters=[MagicMock(spec=OrderUpdater) for _ in range(n_bids)],
        offer_updaters=[MagicMock(spec=OrderUpdater) for _ in range(n_offers)],
        open_bid_ids=[None] * n_bids,
        open_offer_ids=[None] * n_offers,
    )


# ---------------------------------------------------------------------------
# Tests: LocalMarketOrderDispatcher
# ---------------------------------------------------------------------------


class TestLocalMarketOrderDispatcher:

    @staticmethod
    def test_post_bid_calls_market_bid():
        market = make_mock_market()
        dispatcher = LocalMarketOrderDispatcher("owner", "owner-uuid")
        result = dispatcher.post_bid(market, SLOT_START, BID_ENERGY, Decimal("20"))
        market.bid.assert_called_once()
        assert result == "bid-id-001"

    @staticmethod
    def test_post_bid_returns_none_for_zero_energy():
        market = make_mock_market()
        dispatcher = LocalMarketOrderDispatcher("owner", "owner-uuid")
        result = dispatcher.post_bid(market, SLOT_START, 0.0, Decimal("20"))
        market.bid.assert_not_called()
        assert result is None

    @staticmethod
    def test_post_offer_calls_market_offer():
        market = make_mock_market()
        dispatcher = LocalMarketOrderDispatcher("owner", "owner-uuid")
        result = dispatcher.post_offer(market, SLOT_START, OFFER_ENERGY, Decimal("30"))
        market.offer.assert_called_once()
        assert result == "offer-id-001"

    @staticmethod
    def test_post_offer_returns_none_for_zero_energy():
        market = make_mock_market()
        dispatcher = LocalMarketOrderDispatcher("owner", "owner-uuid")
        result = dispatcher.post_offer(market, SLOT_START, 0.0, Decimal("30"))
        market.offer.assert_not_called()
        assert result is None

    @staticmethod
    def test_delete_bid_calls_market_delete_bid():
        market = make_mock_market()
        dispatcher = LocalMarketOrderDispatcher("owner", "owner-uuid")
        dispatcher.delete_bid(market, "some-bid-id")
        market.delete_bid.assert_called_once_with("some-bid-id")

    @staticmethod
    def test_delete_offer_calls_market_delete_offer():
        market = make_mock_market()
        dispatcher = LocalMarketOrderDispatcher("owner", "owner-uuid")
        dispatcher.delete_offer(market, "some-offer-id")
        market.delete_offer.assert_called_once_with("some-offer-id")


# ---------------------------------------------------------------------------
# Tests: ExternalStrategyBase – input updates
# ---------------------------------------------------------------------------


class TestExternalStrategyBaseInputUpdates:

    @staticmethod
    def test_update_bid_inputs_replaces_list():
        strategy = make_strategy()
        new_inputs = [make_bid_input(energy=5.0), make_bid_input(energy=3.0)]
        strategy.update_bid_inputs(new_inputs)
        assert strategy._bid_inputs is new_inputs

    @staticmethod
    def test_update_offer_inputs_replaces_list():
        strategy = make_strategy()
        new_inputs = [make_offer_input(energy=3.0)]
        strategy.update_offer_inputs(new_inputs)
        assert strategy._offer_inputs is new_inputs

    @staticmethod
    def test_default_inputs_are_empty_lists():
        strategy = make_strategy()
        assert strategy._bid_inputs == []
        assert strategy._offer_inputs == []


# ---------------------------------------------------------------------------
# Tests: ExternalStrategyBase – post_order
# ---------------------------------------------------------------------------


class TestExternalStrategyBasePostOrder:

    @staticmethod
    def test_post_order_posts_single_bid():
        dispatcher = MagicMock()
        dispatcher.post_bid.return_value = "bid-id"
        strategy = make_strategy(bid_inputs=[make_bid_input()], dispatcher=dispatcher)
        market = make_mock_market()

        state = make_slot_state_with_updaters(n_bids=1, n_offers=0)
        state.bid_updaters[0].get_energy_rate.return_value = Decimal("20")
        strategy._slot_states[SLOT_START] = state

        strategy.post_order(market, SLOT_START)

        dispatcher.post_bid.assert_called_once()
        assert state.open_bid_ids[0] == "bid-id"

    @staticmethod
    def test_post_order_posts_multiple_bids():
        dispatcher = MagicMock()
        dispatcher.post_bid.side_effect = ["bid-1", "bid-2"]
        strategy = make_strategy(
            bid_inputs=[make_bid_input(energy=1.0), make_bid_input(energy=2.0)],
            dispatcher=dispatcher,
        )
        market = make_mock_market()

        state = make_slot_state_with_updaters(n_bids=2, n_offers=0)
        for u in state.bid_updaters:
            u.get_energy_rate.return_value = Decimal("20")
        strategy._slot_states[SLOT_START] = state

        strategy.post_order(market, SLOT_START)

        assert dispatcher.post_bid.call_count == 2
        assert state.open_bid_ids == ["bid-1", "bid-2"]

    @staticmethod
    def test_post_order_posts_single_offer():
        dispatcher = MagicMock()
        dispatcher.post_offer.return_value = "offer-id"
        strategy = make_strategy(offer_inputs=[make_offer_input()], dispatcher=dispatcher)
        market = make_mock_market()

        state = make_slot_state_with_updaters(n_bids=0, n_offers=1)
        state.offer_updaters[0].get_energy_rate.return_value = Decimal("40")
        strategy._slot_states[SLOT_START] = state

        strategy.post_order(market, SLOT_START)

        dispatcher.post_offer.assert_called_once()
        assert state.open_offer_ids[0] == "offer-id"

    @staticmethod
    def test_post_order_posts_multiple_offers():
        dispatcher = MagicMock()
        dispatcher.post_offer.side_effect = ["offer-1", "offer-2"]
        strategy = make_strategy(
            offer_inputs=[make_offer_input(energy=1.0), make_offer_input(energy=3.0)],
            dispatcher=dispatcher,
        )
        market = make_mock_market()

        state = make_slot_state_with_updaters(n_bids=0, n_offers=2)
        for u in state.offer_updaters:
            u.get_energy_rate.return_value = Decimal("30")
        strategy._slot_states[SLOT_START] = state

        strategy.post_order(market, SLOT_START)

        assert dispatcher.post_offer.call_count == 2
        assert state.open_offer_ids == ["offer-1", "offer-2"]

    @staticmethod
    def test_post_order_uses_given_rate_for_all_orders():
        dispatcher = MagicMock()
        dispatcher.post_bid.side_effect = ["bid-1", "bid-2"]
        strategy = make_strategy(
            bid_inputs=[make_bid_input(), make_bid_input()], dispatcher=dispatcher
        )
        market = make_mock_market()

        state = make_slot_state_with_updaters(n_bids=2, n_offers=0)
        strategy._slot_states[SLOT_START] = state

        strategy.post_order(market, SLOT_START, order_rate=25.0)

        for call in dispatcher.post_bid.call_args_list:
            assert call[0][3] == Decimal("25.0")
        for u in state.bid_updaters:
            u.get_energy_rate.assert_not_called()

    @staticmethod
    def test_post_order_does_nothing_when_no_slot_state():
        dispatcher = MagicMock()
        strategy = make_strategy(bid_inputs=[make_bid_input()], dispatcher=dispatcher)
        market = make_mock_market()

        strategy.post_order(market, SLOT_START)

        dispatcher.post_bid.assert_not_called()
        dispatcher.post_offer.assert_not_called()

    @staticmethod
    def test_post_order_skips_bids_when_bid_inputs_is_empty():
        dispatcher = MagicMock()
        dispatcher.post_offer.return_value = "offer-id"
        strategy = make_strategy(offer_inputs=[make_offer_input()], dispatcher=dispatcher)
        market = make_mock_market()

        state = make_slot_state_with_updaters(n_bids=0, n_offers=1)
        state.offer_updaters[0].get_energy_rate.return_value = Decimal("30")
        strategy._slot_states[SLOT_START] = state

        strategy.post_order(market, SLOT_START)

        dispatcher.post_bid.assert_not_called()
        dispatcher.post_offer.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: ExternalStrategyBase – remove_open_orders / remove_order
# ---------------------------------------------------------------------------


class TestExternalStrategyBaseRemoveOrders:

    @staticmethod
    def test_remove_open_orders_deletes_all_bids_and_offers():
        dispatcher = MagicMock()
        strategy = make_strategy(dispatcher=dispatcher)
        market = make_mock_market()

        state = ExternalOrderSlotState(
            open_bid_ids=["bid-1", "bid-2"],
            open_offer_ids=["offer-1"],
        )
        strategy._slot_states[SLOT_START] = state

        strategy.remove_open_orders(market, SLOT_START)

        assert dispatcher.delete_bid.call_count == 2
        assert dispatcher.delete_offer.call_count == 1
        assert state.open_bid_ids == [None, None]
        assert state.open_offer_ids == [None]

    @staticmethod
    def test_remove_open_orders_skips_none_entries():
        dispatcher = MagicMock()
        strategy = make_strategy(dispatcher=dispatcher)
        market = make_mock_market()

        state = ExternalOrderSlotState(
            open_bid_ids=[None, "bid-2"],
            open_offer_ids=[None],
        )
        strategy._slot_states[SLOT_START] = state

        strategy.remove_open_orders(market, SLOT_START)

        dispatcher.delete_bid.assert_called_once_with(market, "bid-2")
        dispatcher.delete_offer.assert_not_called()

    @staticmethod
    def test_remove_open_orders_does_nothing_for_unknown_slot():
        dispatcher = MagicMock()
        strategy = make_strategy(dispatcher=dispatcher)
        market = make_mock_market()

        strategy.remove_open_orders(market, SLOT_START)

        dispatcher.delete_bid.assert_not_called()
        dispatcher.delete_offer.assert_not_called()

    @staticmethod
    def test_remove_order_deletes_matching_bid():
        dispatcher = MagicMock()
        strategy = make_strategy(dispatcher=dispatcher)
        market = make_mock_market()

        state = ExternalOrderSlotState(
            open_bid_ids=["bid-1", "bid-xyz"],
            open_offer_ids=["offer-xyz"],
        )
        strategy._slot_states[SLOT_START] = state

        strategy.remove_order(market, SLOT_START, "bid-xyz")

        dispatcher.delete_bid.assert_called_once_with(market, "bid-xyz")
        dispatcher.delete_offer.assert_not_called()
        assert state.open_bid_ids == ["bid-1", None]
        assert state.open_offer_ids == ["offer-xyz"]

    @staticmethod
    def test_remove_order_deletes_matching_offer():
        dispatcher = MagicMock()
        strategy = make_strategy(dispatcher=dispatcher)
        market = make_mock_market()

        state = ExternalOrderSlotState(
            open_bid_ids=["bid-xyz"],
            open_offer_ids=["offer-1", "offer-xyz"],
        )
        strategy._slot_states[SLOT_START] = state

        strategy.remove_order(market, SLOT_START, "offer-xyz")

        dispatcher.delete_offer.assert_called_once_with(market, "offer-xyz")
        dispatcher.delete_bid.assert_not_called()
        assert state.open_offer_ids == ["offer-1", None]
        assert state.open_bid_ids == ["bid-xyz"]


# ---------------------------------------------------------------------------
# Tests: ExternalStrategyBase – _open_slot
# ---------------------------------------------------------------------------


class TestExternalStrategyBaseOpenSlot:

    @staticmethod
    def test_open_slot_creates_updaters_and_posts_all_orders():
        dispatcher = MagicMock()
        dispatcher.post_bid.side_effect = ["bid-1", "bid-2"]
        dispatcher.post_offer.side_effect = ["offer-1"]
        strategy = make_strategy(
            bid_inputs=[make_bid_input(energy=1.0), make_bid_input(energy=2.0)],
            offer_inputs=[make_offer_input(energy=3.0)],
            dispatcher=dispatcher,
        )
        market = make_mock_market()

        strategy._open_slot(market)

        state = strategy._slot_states[SLOT_START]
        assert len(state.bid_updaters) == 2
        assert len(state.offer_updaters) == 1
        assert dispatcher.post_bid.call_count == 2
        assert dispatcher.post_offer.call_count == 1

    @staticmethod
    def test_open_slot_is_idempotent():
        dispatcher = MagicMock()
        dispatcher.post_bid.return_value = "bid-id"
        strategy = make_strategy(bid_inputs=[make_bid_input()], dispatcher=dispatcher)
        market = make_mock_market()

        strategy._open_slot(market)
        strategy._open_slot(market)

        assert dispatcher.post_bid.call_count == 1

    @staticmethod
    def test_open_slot_creates_empty_state_when_market_params_none():
        dispatcher = MagicMock()
        strategy = make_strategy(bid_inputs=[make_bid_input()], dispatcher=dispatcher)
        market = make_mock_market()
        market.get_market_parameters_for_market_slot.return_value = None

        strategy._open_slot(market)

        state = strategy._slot_states[SLOT_START]
        assert state.bid_updaters == []
        assert state.open_bid_ids == []
        dispatcher.post_bid.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: ExternalStrategyBase – _clean_past_slot_states
# ---------------------------------------------------------------------------


class TestExternalStrategyBaseCleanPastSlotStates:

    @staticmethod
    def test_removes_expired_slot_states():
        strategy = make_strategy()
        past_slot = SLOT_START.subtract(hours=1)
        future_slot = SLOT_START.add(hours=1)

        strategy._slot_states[past_slot] = ExternalOrderSlotState(
            closing_time=SLOT_START.subtract(minutes=5)
        )
        strategy._slot_states[future_slot] = ExternalOrderSlotState(
            closing_time=SLOT_START.add(hours=2)
        )

        strategy._clean_past_slot_states()

        assert past_slot not in strategy._slot_states
        assert future_slot in strategy._slot_states

    @staticmethod
    def test_keeps_slot_states_without_closing_time():
        strategy = make_strategy()
        strategy._slot_states[SLOT_START] = ExternalOrderSlotState(closing_time=None)

        strategy._clean_past_slot_states()

        assert SLOT_START in strategy._slot_states


# ---------------------------------------------------------------------------
# Tests: ExternalStrategyBase – event_market_cycle / event_tick
# ---------------------------------------------------------------------------


class TestExternalStrategyBaseEvents:

    @staticmethod
    def test_event_market_cycle_opens_slot_for_all_inputs():
        dispatcher = MagicMock()
        dispatcher.post_bid.side_effect = ["bid-1", "bid-2"]
        strategy = make_strategy(
            bid_inputs=[make_bid_input(energy=1.0), make_bid_input(energy=2.0)],
            dispatcher=dispatcher,
        )
        spot_market = make_mock_market()
        strategy.area.spot_market = spot_market

        strategy.event_market_cycle()

        state = strategy._slot_states[SLOT_START]
        assert len(state.bid_updaters) == 2
        assert dispatcher.post_bid.call_count == 2

    @staticmethod
    def test_event_market_cycle_does_nothing_when_no_spot_market():
        strategy = make_strategy()
        strategy.area.spot_market = None

        strategy.event_market_cycle()

        assert not strategy._slot_states

    @staticmethod
    def test_event_tick_updates_all_orders_when_any_updater_is_due():
        dispatcher = MagicMock()
        dispatcher.post_bid.side_effect = ["new-bid-1", "new-bid-2"]
        strategy = make_strategy(
            bid_inputs=[make_bid_input(energy=1.0), make_bid_input(energy=2.0)],
            dispatcher=dispatcher,
        )
        spot_market = make_mock_market()
        strategy.area.spot_market = spot_market

        state = make_slot_state_with_updaters(n_bids=2, n_offers=0)
        state.open_bid_ids = ["old-bid-1", "old-bid-2"]
        state.bid_updaters[0].is_time_for_update.return_value = True
        state.bid_updaters[1].is_time_for_update.return_value = False
        for u in state.bid_updaters:
            u.get_energy_rate.return_value = Decimal("25")
        strategy._slot_states[SLOT_START] = state

        strategy.event_tick()

        assert dispatcher.delete_bid.call_count == 2
        assert dispatcher.post_bid.call_count == 2

    @staticmethod
    def test_event_tick_does_not_update_when_no_updater_is_due():
        dispatcher = MagicMock()
        strategy = make_strategy(bid_inputs=[make_bid_input()], dispatcher=dispatcher)
        spot_market = make_mock_market()
        strategy.area.spot_market = spot_market

        state = make_slot_state_with_updaters(n_bids=1, n_offers=0)
        state.open_bid_ids = ["old-bid-id"]
        state.bid_updaters[0].is_time_for_update.return_value = False
        strategy._slot_states[SLOT_START] = state

        strategy.event_tick()

        dispatcher.delete_bid.assert_not_called()
        dispatcher.post_bid.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: ExternalStrategyBase – serialize
# ---------------------------------------------------------------------------


class TestExternalStrategyBaseSerialize:

    @staticmethod
    def test_serialize_returns_dict():
        strategy = make_strategy()
        result = strategy.serialize()
        assert isinstance(result, dict)
        assert "update_interval" in result
        assert "initial_rate" in result
        assert "final_rate" in result
