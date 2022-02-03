# pylint: disable=protected-access
from unittest.mock import patch

from pendulum import now, duration

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

    @staticmethod
    def _setup_storage_state_for_clamp_energy():
        storage_state = StorageState()
        current_time_slot = now()
        market_slot_list = [current_time_slot,
                            current_time_slot + duration(minutes=15),
                            current_time_slot + duration(minutes=30),
                            current_time_slot + duration(minutes=45)]
        storage_state._current_market_slot = current_time_slot
        storage_state._used_storage = 250.0
        storage_state.capacity = 500.0
        for time_slot in market_slot_list:
            storage_state.offered_sell_kWh[time_slot] = 0.0
            storage_state.pledged_sell_kWh[time_slot] = 0.0
            storage_state.offered_buy_kWh[time_slot] = 0.0
            storage_state.pledged_buy_kWh[time_slot] = 0.0
        return storage_state, market_slot_list

    def test_clamp_energy_to_sell_kWh_only_on_first_slot(self):
        storage_state, market_slot_list = self._setup_storage_state_for_clamp_energy()

        # Enable battery to sell all its available capacity in one market slot
        storage_state._battery_energy_per_slot = storage_state.capacity
        storage_state._clamp_energy_to_sell_kWh(market_slot_list)
        expected_available_energy = (
                storage_state.used_storage -
                storage_state.min_allowed_soc_ratio * storage_state.capacity)
        expected_energy_to_sell = {
            market_slot_list[0]: expected_available_energy,
            market_slot_list[1]: 0.0,
            market_slot_list[2]: 0.0,
            market_slot_list[3]: 0.0,
        }
        assert expected_energy_to_sell == storage_state.energy_to_sell_dict

    def test_clamp_energy_to_sell_kWh_respects_battery_energy_per_slot(self):
        storage_state, market_slot_list = self._setup_storage_state_for_clamp_energy()

        storage_state._battery_energy_per_slot = 25.0
        storage_state._clamp_energy_to_sell_kWh(market_slot_list)
        expected_energy_to_sell = {
            market_slot_list[0]: 25.0,
            market_slot_list[1]: 25.0,
            market_slot_list[2]: 25.0,
            market_slot_list[3]: 25.0,
        }
        assert expected_energy_to_sell == storage_state.energy_to_sell_dict

    def test_clamp_energy_to_sell_kWh_respects_energy_offers_trades(self):
        storage_state, market_slot_list = self._setup_storage_state_for_clamp_energy()

        storage_state._battery_energy_per_slot = 25.0
        for time_slot in market_slot_list:
            storage_state.offered_sell_kWh[time_slot] = 5.0
            storage_state.pledged_sell_kWh[time_slot] = 15.0
        storage_state._clamp_energy_to_sell_kWh(market_slot_list)
        expected_energy_to_sell = {
            market_slot_list[0]: 5.0,
            market_slot_list[1]: 5.0,
            market_slot_list[2]: 5.0,
            market_slot_list[3]: 5.0,
        }
        assert expected_energy_to_sell == storage_state.energy_to_sell_dict

    def test_clamp_energy_to_buy_kWh_only_on_first_slot(self):
        storage_state, market_slot_list = self._setup_storage_state_for_clamp_energy()

        # Enable battery to sell all its available capacity in one market slot
        storage_state._battery_energy_per_slot = storage_state.capacity
        storage_state._clamp_energy_to_buy_kWh(market_slot_list)
        expected_available_energy = storage_state.capacity - storage_state.used_storage
        expected_energy_to_buy = {
            market_slot_list[0]: expected_available_energy,
            market_slot_list[1]: 0.0,
            market_slot_list[2]: 0.0,
            market_slot_list[3]: 0.0,
        }
        assert expected_energy_to_buy == storage_state.energy_to_buy_dict

    def test_clamp_energy_to_buy_kWh_respects_battery_energy_per_slot(self):
        storage_state, market_slot_list = self._setup_storage_state_for_clamp_energy()

        storage_state._battery_energy_per_slot = 25.0
        storage_state._clamp_energy_to_buy_kWh(market_slot_list)
        expected_energy_to_buy = {
            market_slot_list[0]: 25.0,
            market_slot_list[1]: 25.0,
            market_slot_list[2]: 25.0,
            market_slot_list[3]: 25.0,
        }
        assert expected_energy_to_buy == storage_state.energy_to_buy_dict

    def test_clamp_energy_to_buy_kWh_respects_energy_offers_trades(self):
        storage_state, market_slot_list = self._setup_storage_state_for_clamp_energy()

        storage_state._battery_energy_per_slot = 25.0
        for time_slot in market_slot_list:
            storage_state.offered_buy_kWh[time_slot] = 5.0
            storage_state.pledged_buy_kWh[time_slot] = 15.0
        storage_state._clamp_energy_to_buy_kWh(market_slot_list)
        expected_energy_to_buy = {
            market_slot_list[0]: 5.0,
            market_slot_list[1]: 5.0,
            market_slot_list[2]: 5.0,
            market_slot_list[3]: 5.0,
        }
        assert expected_energy_to_buy == storage_state.energy_to_buy_dict
