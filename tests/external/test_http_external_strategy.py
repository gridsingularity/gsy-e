# pylint: disable=missing-function-docstring, protected-access, missing-class-docstring
from decimal import Decimal
from unittest.mock import MagicMock

import pendulum
import pytest

from gsy_e.external.proxy.ewds_strategy import (
    EWDSExternalStrategy,
    HttpOrderInput,
)
from gsy_e.external.proxy.connection import StubEWDSConnection, EWDSMarketSlotInfo
from gsy_e.external.proxy.ewds_strategy import _HttpSlotState
from gsy_e.external.proxy.price_updater import SlotPriceUpdater


SLOT_OPEN = pendulum.datetime(2024, 1, 1, 12, 0, tz="UTC")
SLOT_CLOSE = SLOT_OPEN.add(minutes=15)
DELIVERY_START = SLOT_CLOSE
DELIVERY_END = DELIVERY_START.add(minutes=15)
MARKET_ID = "market-uuid-001"

BID_ENERGY = 1.0
OFFER_ENERGY = 2.0
MIN_PRICE = 10.0
MAX_PRICE = 50.0


def make_slot_info(
    opening=SLOT_OPEN,
    closing=SLOT_CLOSE,
    delivery_start=DELIVERY_START,
    delivery_end=DELIVERY_END,
    market_id=MARKET_ID,
) -> EWDSMarketSlotInfo:
    return EWDSMarketSlotInfo(
        market_id=market_id,
        opening_time=opening,
        closing_time=closing,
        delivery_start_time=delivery_start,
        delivery_end_time=delivery_end,
    )


def make_bid_input(energy=BID_ENERGY, min_price=MIN_PRICE, max_price=MAX_PRICE) -> HttpOrderInput:
    return HttpOrderInput(energy_kWh=energy, min_price=min_price, max_price=max_price)


def make_offer_input(
    energy=OFFER_ENERGY, min_price=MIN_PRICE, max_price=MAX_PRICE
) -> HttpOrderInput:
    return HttpOrderInput(energy_kWh=energy, min_price=min_price, max_price=max_price)


def make_connector(slot_infos=None) -> MagicMock:
    """Return a mock connector whose get_active_market_slots returns slot_infos."""
    connector = MagicMock()
    connector.get_active_market_slots.return_value = (
        [make_slot_info()] if slot_infos is None else slot_infos
    )
    connector.post_bid.return_value = "bid-id-001"
    connector.post_offer.return_value = "offer-id-001"
    return connector


def make_strategy(bid_inputs=None, offer_inputs=None, connector=None) -> EWDSExternalStrategy:
    if connector is None:
        connector = make_connector()
    return EWDSExternalStrategy(
        connector=connector,
        bid_inputs=bid_inputs,
        offer_inputs=offer_inputs,
    )


class TestSlotPriceUpdater:

    @staticmethod
    def test_returns_initial_rate_at_opening():
        updater = SlotPriceUpdater(
            initial_rate=Decimal("10"),
            final_rate=Decimal("50"),
            opening_time=SLOT_OPEN,
            closing_time=SLOT_CLOSE,
            update_interval=pendulum.duration(minutes=5),
        )
        assert updater.get_rate(SLOT_OPEN) == Decimal("10")

    @staticmethod
    def test_returns_final_rate_at_effective_end():
        interval = pendulum.duration(minutes=5)
        updater = SlotPriceUpdater(
            initial_rate=Decimal("10"),
            final_rate=Decimal("50"),
            opening_time=SLOT_OPEN,
            closing_time=SLOT_CLOSE,
            update_interval=interval,
        )
        effective_end = SLOT_CLOSE - interval
        assert updater.get_rate(effective_end) == Decimal("50")

    @staticmethod
    def test_rate_increases_for_bid():
        interval = pendulum.duration(minutes=5)
        updater = SlotPriceUpdater(
            initial_rate=Decimal("10"),
            final_rate=Decimal("50"),
            opening_time=SLOT_OPEN,
            closing_time=SLOT_CLOSE,
            update_interval=interval,
        )
        mid = SLOT_OPEN.add(minutes=5)
        rate = updater.get_rate(mid)
        assert Decimal("10") < rate < Decimal("50")

    @staticmethod
    def test_rate_decreases_for_offer():
        interval = pendulum.duration(minutes=5)
        updater = SlotPriceUpdater(
            initial_rate=Decimal("50"),
            final_rate=Decimal("10"),
            opening_time=SLOT_OPEN,
            closing_time=SLOT_CLOSE,
            update_interval=interval,
        )
        mid = SLOT_OPEN.add(minutes=5)
        rate = updater.get_rate(mid)
        assert Decimal("10") < rate < Decimal("50")

    @staticmethod
    def test_is_time_for_update_at_opening():
        updater = SlotPriceUpdater(
            initial_rate=Decimal("10"),
            final_rate=Decimal("50"),
            opening_time=SLOT_OPEN,
            closing_time=SLOT_CLOSE,
            update_interval=pendulum.duration(minutes=5),
        )
        assert updater.is_time_for_update(SLOT_OPEN) is True

    @staticmethod
    def test_is_time_for_update_false_between_timepoints():
        updater = SlotPriceUpdater(
            initial_rate=Decimal("10"),
            final_rate=Decimal("50"),
            opening_time=SLOT_OPEN,
            closing_time=SLOT_CLOSE,
            update_interval=pendulum.duration(minutes=5),
        )
        between = SLOT_OPEN.add(minutes=2)
        assert updater.is_time_for_update(between) is False

    @staticmethod
    def test_get_rate_before_opening_returns_initial():
        updater = SlotPriceUpdater(
            initial_rate=Decimal("10"),
            final_rate=Decimal("50"),
            opening_time=SLOT_OPEN,
            closing_time=SLOT_CLOSE,
            update_interval=pendulum.duration(minutes=5),
        )
        before = SLOT_OPEN.subtract(minutes=1)
        assert updater.get_rate(before) == Decimal("10")

    @staticmethod
    def test_get_rate_after_effective_end_returns_final():
        interval = pendulum.duration(minutes=5)
        updater = SlotPriceUpdater(
            initial_rate=Decimal("10"),
            final_rate=Decimal("50"),
            opening_time=SLOT_OPEN,
            closing_time=SLOT_CLOSE,
            update_interval=interval,
        )
        after = SLOT_CLOSE  # past effective_end
        assert updater.get_rate(after) == Decimal("50")


class TestStubEWDSConnection:

    @staticmethod
    def test_all_methods_raise_not_implemented():
        connector = StubEWDSConnection(created_by="trader-1")
        slot = SLOT_OPEN
        with pytest.raises(NotImplementedError):
            connector.get_active_market_slots()
        with pytest.raises(NotImplementedError):
            connector.post_bid(MARKET_ID, slot, 1.0, Decimal("20"))
        with pytest.raises(NotImplementedError):
            connector.post_offer(MARKET_ID, slot, 1.0, Decimal("20"))
        with pytest.raises(NotImplementedError):
            connector.delete_bid(slot, "id")
        with pytest.raises(NotImplementedError):
            connector.delete_offer(slot, "id")


class TestHttpExternalStrategyInputUpdates:

    @staticmethod
    def test_default_inputs_are_empty():
        strategy = make_strategy()
        assert strategy._bid_inputs == []
        assert strategy._offer_inputs == []

    @staticmethod
    def test_update_bid_inputs_replaces_list():
        strategy = make_strategy()
        new_inputs = [make_bid_input(energy=3.0)]
        strategy.update_bid_inputs(new_inputs)
        assert strategy._bid_inputs is new_inputs

    @staticmethod
    def test_update_offer_inputs_replaces_list():
        strategy = make_strategy()
        new_inputs = [make_offer_input(energy=5.0)]
        strategy.update_offer_inputs(new_inputs)
        assert strategy._offer_inputs is new_inputs


class TestHttpExternalStrategyOnMarketCycle:

    @staticmethod
    def test_opens_slot_and_posts_bid():
        connector = make_connector()
        connector.post_bid.return_value = "bid-1"
        strategy = make_strategy(bid_inputs=[make_bid_input()], connector=connector)

        strategy.on_market_cycle(SLOT_OPEN)

        connector.post_bid.assert_called_once()
        assert SLOT_OPEN in strategy._slot_states

    @staticmethod
    def test_opens_slot_and_posts_offer():
        connector = make_connector()
        connector.post_offer.return_value = "offer-1"
        strategy = make_strategy(offer_inputs=[make_offer_input()], connector=connector)

        strategy.on_market_cycle(SLOT_OPEN)

        connector.post_offer.assert_called_once()
        assert SLOT_OPEN in strategy._slot_states

    @staticmethod
    def test_posts_multiple_bids_and_offers():
        connector = make_connector()
        connector.post_bid.side_effect = ["bid-1", "bid-2"]
        connector.post_offer.return_value = "offer-1"
        strategy = make_strategy(
            bid_inputs=[make_bid_input(energy=1.0), make_bid_input(energy=2.0)],
            offer_inputs=[make_offer_input(energy=3.0)],
            connector=connector,
        )

        strategy.on_market_cycle(SLOT_OPEN)

        assert connector.post_bid.call_count == 2
        assert connector.post_offer.call_count == 1
        state = strategy._slot_states[SLOT_OPEN]
        assert state.open_bid_ids == ["bid-1", "bid-2"]
        assert state.open_offer_ids == ["offer-1"]

    @staticmethod
    def test_is_idempotent_for_same_slot():
        connector = make_connector()
        connector.post_bid.return_value = "bid-1"
        strategy = make_strategy(bid_inputs=[make_bid_input()], connector=connector)

        strategy.on_market_cycle(SLOT_OPEN)
        strategy.on_market_cycle(SLOT_OPEN)

        assert connector.post_bid.call_count == 1

    @staticmethod
    def test_cleans_expired_slots():
        past_slot_open = SLOT_OPEN.subtract(hours=1)
        past_slot_close = past_slot_open.add(minutes=15)
        past_slot_info = make_slot_info(
            opening=past_slot_open,
            closing=past_slot_close,
            delivery_start=past_slot_close,
            delivery_end=past_slot_close.add(minutes=15),
        )
        connector = make_connector(slot_infos=[make_slot_info()])
        strategy = make_strategy(bid_inputs=[make_bid_input()], connector=connector)

        strategy._slot_states[past_slot_open] = _HttpSlotState(slot_info=past_slot_info)

        strategy.on_market_cycle(SLOT_OPEN)

        assert past_slot_open not in strategy._slot_states
        assert SLOT_OPEN in strategy._slot_states


class TestHttpExternalStrategyOnTick:

    @staticmethod
    def test_updates_orders_when_updater_is_due():
        connector = make_connector()
        connector.post_bid.side_effect = ["old-bid", "new-bid"]
        strategy = make_strategy(bid_inputs=[make_bid_input()], connector=connector)

        strategy.on_market_cycle(SLOT_OPEN)

        # Advance to the first scheduled update timepoint after opening
        tick = SLOT_OPEN.add(minutes=5)
        strategy.on_tick(tick)

        assert connector.delete_bid.call_count == 1
        assert connector.post_bid.call_count == 2

    @staticmethod
    def test_does_not_update_between_timepoints():
        connector = make_connector()
        connector.post_bid.return_value = "bid-1"
        strategy = make_strategy(bid_inputs=[make_bid_input()], connector=connector)

        strategy.on_market_cycle(SLOT_OPEN)

        # Tick at a time that is not a scheduled update point
        between = SLOT_OPEN.add(minutes=2)
        strategy.on_tick(between)

        connector.delete_bid.assert_not_called()
        assert connector.post_bid.call_count == 1  # only the initial post

    @staticmethod
    def test_no_op_when_no_slot_states():
        connector = make_connector(slot_infos=[])
        strategy = make_strategy(bid_inputs=[make_bid_input()], connector=connector)

        strategy.on_market_cycle(SLOT_OPEN)
        strategy.on_tick(SLOT_OPEN.add(minutes=5))

        connector.delete_bid.assert_not_called()
        connector.post_bid.assert_not_called()


class TestHttpExternalStrategyTraded:

    @staticmethod
    def test_on_bid_traded_reduces_remaining_energy():
        connector = make_connector()
        strategy = make_strategy(bid_inputs=[make_bid_input(energy=2.0)], connector=connector)
        strategy.on_market_cycle(SLOT_OPEN)

        strategy.on_bid_traded(SLOT_OPEN, 0.5)

        assert strategy._slot_states[SLOT_OPEN].remaining_bid_energy_kWh == pytest.approx(1.5)

    @staticmethod
    def test_on_offer_traded_reduces_remaining_energy():
        connector = make_connector()
        strategy = make_strategy(offer_inputs=[make_offer_input(energy=3.0)], connector=connector)
        strategy.on_market_cycle(SLOT_OPEN)

        strategy.on_offer_traded(SLOT_OPEN, 1.0)

        assert strategy._slot_states[SLOT_OPEN].remaining_offer_energy_kWh == pytest.approx(2.0)

    @staticmethod
    def test_remaining_energy_does_not_go_negative():
        connector = make_connector()
        strategy = make_strategy(bid_inputs=[make_bid_input(energy=1.0)], connector=connector)
        strategy.on_market_cycle(SLOT_OPEN)

        strategy.on_bid_traded(SLOT_OPEN, 999.0)

        assert strategy._slot_states[SLOT_OPEN].remaining_bid_energy_kWh == 0.0

    @staticmethod
    def test_traded_for_unknown_slot_is_silently_ignored():
        connector = make_connector()
        strategy = make_strategy(bid_inputs=[make_bid_input()], connector=connector)

        unknown_slot = SLOT_OPEN.add(hours=10)
        strategy.on_bid_traded(unknown_slot, 1.0)  # must not raise

    @staticmethod
    def test_subsequent_post_uses_reduced_energy():
        connector = make_connector()
        connector.post_bid.side_effect = ["bid-1", "bid-2"]
        strategy = make_strategy(bid_inputs=[make_bid_input(energy=2.0)], connector=connector)

        strategy.on_market_cycle(SLOT_OPEN)
        strategy.on_bid_traded(SLOT_OPEN, 1.0)

        # Trigger a price update to cause a re-post
        update_tick = SLOT_OPEN.add(minutes=5)
        strategy.on_tick(update_tick)

        # Second post_bid call should use the reduced remaining energy (1.0 kWh)
        second_call_args = connector.post_bid.call_args_list[1]
        posted_energy = second_call_args[0][
            2
        ]  # positional arg: energy_kWh (after market_id, time_slot)
        assert posted_energy == pytest.approx(1.0)


class TestHttpExternalStrategyCancelOrders:

    @staticmethod
    def test_cancel_continues_after_connector_error():
        connector = make_connector()
        connector.post_bid.side_effect = ["bid-1", "bid-2"]
        connector.delete_bid.side_effect = [Exception("network error"), None]
        strategy = make_strategy(
            bid_inputs=[make_bid_input(energy=1.0), make_bid_input(energy=1.0)],
            connector=connector,
        )

        strategy.on_market_cycle(SLOT_OPEN)

        connector.post_bid.side_effect = ["new-bid-1", "new-bid-2"]
        strategy.on_tick(SLOT_OPEN.add(minutes=5))

        # Both deletes were attempted despite the first failing
        assert connector.delete_bid.call_count == 2
