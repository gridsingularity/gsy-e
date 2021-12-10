from unittest.mock import patch

from pendulum import now

from gsy_e.models.state import StorageState


class TestStorageState:
    """Test the StorageState class."""

    @staticmethod
    def test_market_cycle():
        """Test the market cycle handler of the storage state.

        TODO: Cover the whole module in context of GSY-E:92
        """
        storage_state = StorageState()
        past_time_slot = now()
        current_time_slot = past_time_slot.add(minutes=15)
        future_time_slots = [current_time_slot.add(minutes=15),
                             current_time_slot.add(minutes=30)]
        storage_state.add_default_values_to_state_profiles(
            [past_time_slot, current_time_slot, *future_time_slots])
        storage_state.offered_buy_kWh[future_time_slots[0]] = 10
        storage_state.offered_sell_kWh[future_time_slots[0]] = 10
        with patch("gsy_e.models.state.GlobalConfig.FUTURE_MARKET_DURATION_HOURS", 5):
            storage_state.market_cycle(past_time_slot, current_time_slot, future_time_slots)
            # The future_time_slots[0] is in the future, so it won't reset
            assert storage_state.offered_buy_kWh[future_time_slots[0]] == 10
            assert storage_state.offered_sell_kWh[future_time_slots[0]] == 10
            storage_state.market_cycle(
                current_time_slot, future_time_slots[0], future_time_slots[1:])
            # The future_time_slots[0] is in the spot market, so it has to reset the orders
            assert storage_state.offered_buy_kWh[future_time_slots[0]] == 0
            assert storage_state.offered_sell_kWh[future_time_slots[0]] == 0
