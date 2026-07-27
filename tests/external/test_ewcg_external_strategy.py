# pylint: disable=missing-function-docstring, protected-access, missing-class-docstring
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock, patch

import pendulum
import pytest

from gsy_e.external.proxy.ewcg_strategy import (
    EWCGExternalStrategy,
    OrderInput,
    MarketSlotState,
    TIMEZONE,
)
from gsy_e.external.proxy.dataclasses import MarketSlotInfo, EnergyTrade
from gsy_e.external.proxy.price_updater import SlotPriceUpdater


SLOT_OPEN = pendulum.datetime(2024, 1, 1, 12, 0, tz=TIMEZONE)
SLOT_CLOSE = SLOT_OPEN.add(minutes=15)
DELIVERY_START = SLOT_CLOSE
DELIVERY_END = DELIVERY_START.add(minutes=15)
MARKET_ID = "market-uuid-001"
COMMUNITY_ID = "community-uuid"

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
) -> MarketSlotInfo:
    return MarketSlotInfo(
        market_id=market_id,
        community_id=COMMUNITY_ID,
        opening_time=opening,
        closing_time=closing,
        delivery_start_time=delivery_start,
        delivery_end_time=delivery_end,
    )


def make_bid_input(energy=BID_ENERGY, min_price=MIN_PRICE, max_price=MAX_PRICE) -> OrderInput:
    return OrderInput(
        energy_kWh=energy, min_price=min_price, max_price=max_price, time_slot=DELIVERY_START
    )


def make_offer_input(energy=OFFER_ENERGY, min_price=MIN_PRICE, max_price=MAX_PRICE) -> OrderInput:
    return OrderInput(
        energy_kWh=energy, min_price=min_price, max_price=max_price, time_slot=DELIVERY_START
    )


def make_connector() -> MagicMock:
    """Return a mock connector."""
    connector = MagicMock()
    connector.post_bid.return_value = "bid-id-001"
    connector.post_offer.return_value = "offer-id-001"
    return connector


def make_strategy(bid_inputs=None, offer_inputs=None, connector=None) -> EWCGExternalStrategy:
    if connector is None:
        connector = make_connector()
    return EWCGExternalStrategy(
        connector=connector,
        bid_inputs=bid_inputs,
        offer_inputs=offer_inputs,
    )


def _get_state(strategy: EWCGExternalStrategy, opening_time) -> MarketSlotState:
    """Return the MarketSlotState for the given slot opening time."""
    return next(s for s in strategy._slot_states if s.slot_info.opening_time == opening_time)


def _has_slot(strategy: EWCGExternalStrategy, opening_time) -> bool:
    """Return True if a slot with the given opening time is tracked."""
    return any(s.slot_info.opening_time == opening_time for s in strategy._slot_states)


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


class TestEWCGExternalStrategy:

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

    @staticmethod
    def test_opens_slot_and_posts_bid():
        connector = make_connector()
        connector.post_bid.return_value = "bid-1"
        strategy = make_strategy(bid_inputs=[make_bid_input()], connector=connector)

        slot = make_slot_info(opening=SLOT_OPEN, closing=SLOT_CLOSE)
        with patch.object(strategy, "_clean_expired_slots"):
            strategy.on_market_slot(slot)

        connector.post_bid.assert_called_once()
        assert _has_slot(strategy, SLOT_OPEN)

    @staticmethod
    def test_opens_slot_and_posts_offer():
        connector = make_connector()
        connector.post_offer.return_value = "offer-1"
        strategy = make_strategy(offer_inputs=[make_offer_input()], connector=connector)

        slot = make_slot_info(opening=SLOT_OPEN, closing=SLOT_CLOSE)
        with patch.object(strategy, "_clean_expired_slots"):
            strategy.on_market_slot(slot)

        connector.post_offer.assert_called_once()
        assert _has_slot(strategy, SLOT_OPEN)

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

        slot = make_slot_info(opening=SLOT_OPEN, closing=SLOT_CLOSE)
        with patch.object(strategy, "_clean_expired_slots"):
            strategy.on_market_slot(slot)

        assert connector.post_bid.call_count == 2
        assert connector.post_offer.call_count == 1
        state = _get_state(strategy, SLOT_OPEN)
        assert state.open_bid_ids == ["bid-1", "bid-2"]
        assert state.open_offer_ids == ["offer-1"]

    @staticmethod
    def test_is_idempotent_for_same_slot():
        connector = make_connector()
        connector.post_bid.return_value = "bid-1"
        strategy = make_strategy(bid_inputs=[make_bid_input()], connector=connector)

        slot = make_slot_info(opening=SLOT_OPEN, closing=SLOT_CLOSE)
        with patch.object(strategy, "_clean_expired_slots"):
            strategy.on_market_slot(slot)
            strategy.on_market_slot(slot)

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
        connector = make_connector()
        strategy = make_strategy(bid_inputs=[make_bid_input()], connector=connector)

        strategy._slot_states.append(MarketSlotState(slot_info=past_slot_info))

        slot = make_slot_info(opening=SLOT_OPEN, closing=SLOT_CLOSE)
        strategy.on_market_slot(slot)

        assert not _has_slot(strategy, past_slot_open)
        assert _has_slot(strategy, SLOT_OPEN)

    @staticmethod
    def test_updates_orders_when_updater_is_due():
        connector = make_connector()
        connector.post_bid.side_effect = ["old-bid", "new-bid"]
        strategy = make_strategy(bid_inputs=[make_bid_input()], connector=connector)

        slot = make_slot_info()
        with patch.object(strategy, "_clean_expired_slots"):
            strategy.on_market_slot(slot)

        # Advance to the first scheduled update timepoint after opening
        tick = SLOT_OPEN.add(minutes=5)
        with patch.object(type(strategy), "now", new_callable=PropertyMock, return_value=tick):
            strategy.on_tick()

        assert connector.delete_bid.call_count == 1
        assert connector.post_bid.call_count == 2

    @staticmethod
    def test_does_not_update_between_timepoints():
        connector = make_connector()
        connector.post_bid.return_value = "bid-1"
        strategy = make_strategy(bid_inputs=[make_bid_input()], connector=connector)

        slot = make_slot_info(opening=SLOT_OPEN, closing=SLOT_CLOSE)
        with patch.object(strategy, "_clean_expired_slots"):
            strategy.on_market_slot(slot)

        # Tick at a time that is not a scheduled update point
        between = SLOT_OPEN.add(minutes=2)
        with patch.object(type(strategy), "now", new_callable=PropertyMock, return_value=between):
            strategy.on_tick()

        connector.delete_bid.assert_not_called()
        assert connector.post_bid.call_count == 1  # only the initial post

    @staticmethod
    def test_on_order_traded_for_bid_reduces_remaining_energy():
        connector = make_connector()
        bid = make_bid_input(energy=2.0)
        strategy = make_strategy(bid_inputs=[bid], connector=connector)

        slot = make_slot_info(opening=SLOT_OPEN, closing=SLOT_CLOSE)
        with patch.object(strategy, "_clean_expired_slots"):
            strategy.on_market_slot(slot)

        strategy.on_order_traded(
            EnergyTrade(
                market_id=MARKET_ID,
                bid_id="bid-id-001",  # matches connector.post_bid.return_value
                offer_id="offer-id-001",
                residual_bid_id=None,
                residual_offer_id=None,
                energy_kWh=0.5,
                price=10,
                buyer="buyer",
                seller="seller",
            )
        )

        assert _get_state(strategy, SLOT_OPEN).remaining_bid_energy_kWh == pytest.approx(1.5)

    @staticmethod
    def test_on_offer_traded_reduces_remaining_energy():
        connector = make_connector()
        strategy = make_strategy(offer_inputs=[make_offer_input(energy=3.0)], connector=connector)

        slot = make_slot_info()
        with patch.object(strategy, "_clean_expired_slots"):
            strategy.on_market_slot(slot)

        strategy.on_order_traded(
            EnergyTrade(
                market_id=MARKET_ID,
                offer_id="offer-id-001",
                bid_id="not-a-bid",
                price=0.0,
                energy_kWh=1.0,
                seller="seller",
                buyer="buyer",
                residual_offer_id=None,
                residual_bid_id=None,
            )
        )

        assert _get_state(strategy, SLOT_OPEN).remaining_offer_energy_kWh == pytest.approx(2.0)

    @staticmethod
    def test_remaining_energy_does_not_go_negative():
        connector = make_connector()
        strategy = make_strategy(bid_inputs=[make_bid_input(energy=1.0)], connector=connector)

        slot = make_slot_info()
        with patch.object(strategy, "_clean_expired_slots"):
            strategy.on_market_slot(slot)

        strategy.on_order_traded(
            EnergyTrade(
                market_id=MARKET_ID,
                bid_id="bid-id-001",
                offer_id="not-an-offer",
                price=0.0,
                energy_kWh=999.0,
                seller="seller",
                buyer="buyer",
                residual_offer_id=None,
                residual_bid_id=None,
            )
        )

        assert _get_state(strategy, SLOT_OPEN).remaining_bid_energy_kWh == 0.0

    @staticmethod
    def test_traded_for_unknown_slot_is_silently_ignored():
        connector = make_connector()
        strategy = make_strategy(bid_inputs=[make_bid_input()], connector=connector)

        strategy.on_order_traded(
            EnergyTrade(
                market_id="unknown-market-id",
                bid_id="bid-id-001",
                offer_id="not-an-offer",
                price=0.0,
                energy_kWh=1.0,
                seller="seller",
                buyer="buyer",
                residual_offer_id=None,
                residual_bid_id=None,
            )
        )  # must not raise

    @staticmethod
    def test_subsequent_post_uses_reduced_energy():
        connector = make_connector()
        connector.post_bid.side_effect = ["bid-1", "bid-2"]
        strategy = make_strategy(bid_inputs=[make_bid_input(energy=2.0)], connector=connector)

        slot = make_slot_info()
        with patch.object(strategy, "_clean_expired_slots"):
            strategy.on_market_slot(slot)

        strategy.on_order_traded(
            EnergyTrade(
                market_id=MARKET_ID,
                bid_id="bid-1",
                offer_id="not-an-offer",
                price=0.0,
                energy_kWh=1.0,
                seller="seller",
                buyer="buyer",
                residual_offer_id=None,
                residual_bid_id=None,
            )
        )

        # Trigger a price update to cause a re-post
        update_tick = SLOT_OPEN.add(minutes=5)
        with patch.object(
            type(strategy), "now", new_callable=PropertyMock, return_value=update_tick
        ):
            strategy.on_tick()

        # Second post_bid call should use the reduced remaining energy (1.0 kWh)
        second_call_args = connector.post_bid.call_args_list[1]
        posted_energy = second_call_args[0][
            2
        ]  # positional arg: energy_kWh (after market_id, time_slot)
        assert posted_energy == pytest.approx(1.0)

    @staticmethod
    def test_cancel_continues_after_connector_error():
        connector = make_connector()
        connector.post_bid.side_effect = ["bid-1", "bid-2"]
        connector.delete_bid.side_effect = [Exception("network error"), None]
        strategy = make_strategy(
            bid_inputs=[make_bid_input(energy=1.0), make_bid_input(energy=1.0)],
            connector=connector,
        )

        slot = make_slot_info()
        with patch.object(strategy, "_clean_expired_slots"):
            strategy.on_market_slot(slot)

        connector.post_bid.side_effect = ["new-bid-1", "new-bid-2"]
        update_tick = SLOT_OPEN.add(minutes=5)
        with patch.object(
            type(strategy), "now", new_callable=PropertyMock, return_value=update_tick
        ):
            strategy.on_tick()

        # Both deletes were attempted despite the first failing
        assert connector.delete_bid.call_count == 2
