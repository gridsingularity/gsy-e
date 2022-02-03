# pylint: disable=protected-access
from unittest.mock import patch

import pytest
from pendulum import now, duration

from gsy_e.models.state import StorageState, ESSEnergyOrigin


class TestStorageState:
    """Test the StorageState class."""

    def test_market_cycle_reset_orders(self):
        """Test the market cycle handler of the storage state.

        TODO: Cover the whole module in context of GSY-E:92
        """
        storage_state = StorageState()
        past_time_slot, current_time_slot, future_time_slots = self._initialize_time_slots()
        active_market_slot_time_list = [past_time_slot, current_time_slot, *future_time_slots]
        storage_state.add_default_values_to_state_profiles(active_market_slot_time_list)
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

    def test_market_cycle_update_used_storage(self):
        storage_state = StorageState(initial_soc=100,
                                     capacity=100)
        past_time_slot, current_time_slot, future_time_slots = self._initialize_time_slots()
        active_market_slot_time_list = [past_time_slot, current_time_slot, *future_time_slots]
        storage_state.add_default_values_to_state_profiles(active_market_slot_time_list)
        storage_state.pledged_sell_kWh[past_time_slot] = 10
        storage_state.pledged_buy_kWh[past_time_slot] = 0
        storage_state.market_cycle(past_time_slot, current_time_slot, future_time_slots)
        assert storage_state.used_storage == 90
        storage_state.pledged_sell_kWh[past_time_slot] = 0
        storage_state.pledged_buy_kWh[past_time_slot] = 10
        storage_state.market_cycle(past_time_slot, current_time_slot, future_time_slots)
        assert storage_state.used_storage == 100

    def test_market_cycle_ess_share_time_series_dict(self):
        storage_state = StorageState(initial_soc=100,
                                     capacity=100,
                                     initial_energy_origin=ESSEnergyOrigin.LOCAL)
        past_time_slot, current_time_slot, future_time_slots = self._initialize_time_slots()
        active_market_slot_time_list = [past_time_slot, current_time_slot, *future_time_slots]
        storage_state.add_default_values_to_state_profiles(active_market_slot_time_list)
        energy = 10
        storage_state.activate(
            slot_length=duration(minutes=15), current_time_slot=current_time_slot)
        storage_state.register_energy_from_one_sided_market_accept_offer(
            energy, past_time_slot, ESSEnergyOrigin.LOCAL)
        storage_state.register_energy_from_one_sided_market_accept_offer(
            energy, past_time_slot, ESSEnergyOrigin.UNKNOWN)
        storage_state.register_energy_from_one_sided_market_accept_offer(
            energy, past_time_slot, ESSEnergyOrigin.UNKNOWN)
        storage_state.market_cycle(past_time_slot, current_time_slot, future_time_slots)
        expected_time_series = {ESSEnergyOrigin.LOCAL: storage_state.initial_capacity_kWh + energy,
                                ESSEnergyOrigin.EXTERNAL: 0.0,
                                ESSEnergyOrigin.UNKNOWN: 2 * energy}
        assert storage_state.time_series_ess_share[past_time_slot] == expected_time_series

    def test_market_cycle_clamp_energy_to_sell_kwh(self):
        storage_state = StorageState(initial_soc=100,
                                     capacity=100,
                                     min_allowed_soc=20)
        past_time_slot, current_time_slot, future_time_slots = self._initialize_time_slots()
        active_market_slot_time_list = [past_time_slot, current_time_slot, *future_time_slots]
        storage_state.add_default_values_to_state_profiles(active_market_slot_time_list)
        storage_state.activate(
            slot_length=duration(minutes=15), current_time_slot=current_time_slot)
        # Scenario in which available energy for all slots < -FLOATING_POINT_TOLERANCE
        for time_slot in active_market_slot_time_list:
            storage_state.pledged_sell_kWh[time_slot] = 20
            storage_state.offered_sell_kWh[time_slot] = 20
        storage_state.market_cycle(past_time_slot=None,
                                   current_time_slot=current_time_slot,
                                   all_future_time_slots=future_time_slots)
        for time_slot in [current_time_slot, *future_time_slots]:
            assert storage_state.energy_to_sell_dict.get(time_slot, 1) == 0
        # Scenario in which available energy for all slots > -FLOATING_POINT_TOLERANCE
        for time_slot in active_market_slot_time_list:
            storage_state.pledged_sell_kWh[time_slot] = 5
            storage_state.offered_sell_kWh[time_slot] = 5
        storage_state.market_cycle(past_time_slot=None,
                                   current_time_slot=current_time_slot,
                                   all_future_time_slots=future_time_slots)
        for time_slot in [current_time_slot, *future_time_slots]:
            # assert storage_state.energy_to_sell_dict.get(time_slot, 0) > 0
            assert storage_state.energy_to_sell_dict.get(time_slot) == \
                   storage_state._max_offer_energy_kWh(time_slot) \
                   or storage_state.energy_to_sell_dict.get(time_slot) == \
                   storage_state._battery_energy_per_slot(time_slot) \
                   or storage_state.energy_to_sell_dict.get(time_slot) != 0

    def test_market_cycle_clamp_energy_to_buy_kwh(self):
        storage_state = StorageState(initial_soc=50,
                                     capacity=100,
                                     min_allowed_soc=20)
        past_time_slot, current_time_slot, future_time_slots = self._initialize_time_slots()
        active_market_slot_time_list = [past_time_slot, current_time_slot, *future_time_slots]
        storage_state.add_default_values_to_state_profiles(active_market_slot_time_list)
        storage_state.activate(
            slot_length=duration(minutes=15), current_time_slot=current_time_slot)
        # Scenario in which available energy for all slots < -FLOATING_POINT_TOLERANCE
        for time_slot in active_market_slot_time_list:
            storage_state.pledged_buy_kWh[time_slot] = 20
            storage_state.offered_buy_kWh[time_slot] = 20
        storage_state.market_cycle(past_time_slot=None,
                                   current_time_slot=current_time_slot,
                                   all_future_time_slots=future_time_slots)
        for time_slot in [current_time_slot, *future_time_slots]:
            assert storage_state.energy_to_buy_dict.get(time_slot) == 0
        # Scenario in which available energy for all slots > -FLOATING_POINT_TOLERANCE
        for time_slot in active_market_slot_time_list:
            storage_state.pledged_buy_kWh[time_slot] = 5
            storage_state.offered_buy_kWh[time_slot] = 5
        storage_state.market_cycle(past_time_slot=None,
                                   current_time_slot=current_time_slot,
                                   all_future_time_slots=future_time_slots)
        for time_slot in [current_time_slot, *future_time_slots]:
            assert storage_state.energy_to_sell_dict.get(time_slot, -1) >= 0

    def test_market_cycle_calculate_and_update_soc_and_set_offer_history(self):
        storage_state = StorageState(initial_soc=100,
                                     capacity=100,
                                     min_allowed_soc=20)
        past_time_slot, current_time_slot, future_time_slots = self._initialize_time_slots()
        active_market_slot_time_list = [past_time_slot, current_time_slot, *future_time_slots]
        storage_state.add_default_values_to_state_profiles(active_market_slot_time_list)
        storage_state.activate(
            slot_length=duration(minutes=15), current_time_slot=current_time_slot)
        storage_state.pledged_sell_kWh[past_time_slot] = 10
        storage_state.market_cycle(past_time_slot, current_time_slot, future_time_slots)
        assert storage_state.charge_history[current_time_slot] != storage_state.initial_soc
        assert storage_state.charge_history_kWh[current_time_slot] != \
               storage_state.initial_capacity_kWh
        assert storage_state.offered_history[current_time_slot] != "-"

    @staticmethod
    def _initialize_time_slots():
        past_time_slot = now()
        current_time_slot = past_time_slot.add(minutes=15)
        future_time_slots = [current_time_slot.add(minutes=15),
                             current_time_slot.add(minutes=30)]
        return past_time_slot, current_time_slot, future_time_slots

    @staticmethod
    def test_check_state_charge_less_than_min_soc_error():
        storage_state = StorageState(capacity=100,
                                     min_allowed_soc=50,
                                     initial_soc=30)
        current_time_slot = now()
        storage_state.add_default_values_to_state_profiles([current_time_slot])
        storage_state.activate(
            slot_length=duration(minutes=15), current_time_slot=current_time_slot)
        with pytest.raises(AssertionError) as error:
            storage_state.check_state(current_time_slot)
        assert "less than min soc" in str(error.value)

    @staticmethod
    def test_check_state_storage_surpasses_capacity_error():
        storage_state = StorageState(capacity=100,
                                     min_allowed_soc=50,
                                     initial_soc=110)
        current_time_slot = now()
        storage_state.add_default_values_to_state_profiles([current_time_slot])
        storage_state.activate(
            slot_length=duration(minutes=15), current_time_slot=current_time_slot)
        with pytest.raises(AssertionError) as error:
            storage_state.check_state(current_time_slot)
        assert "surpassed the capacity" in str(error.value)

    @staticmethod
    def test_check_state_offered_and_pledged_energy_in_range():
        storage_state = StorageState(capacity=100,
                                     min_allowed_soc=20,
                                     initial_soc=50)

        current_time_slot = now()
        storage_state.add_default_values_to_state_profiles([current_time_slot])
        storage_state.activate(
            slot_length=duration(minutes=15), current_time_slot=current_time_slot)
        max_value = storage_state.capacity * (1 - storage_state.min_allowed_soc_ratio)

        def set_attribute_value_and_test(attribute):
            attribute[current_time_slot] = -1
            # check that error is raised for value < 0
            with pytest.raises(AssertionError):
                storage_state.check_state(current_time_slot)
            attribute[current_time_slot] = max_value + 1
            # check that error is raised for value > max_value
            with pytest.raises(AssertionError):
                storage_state.check_state(current_time_slot)
            attribute[current_time_slot] = max_value/2
            # check that for value in range no error is raised
            try:
                storage_state.check_state(current_time_slot)
            except AssertionError as error:
                raise AssertionError from error

        set_attribute_value_and_test(storage_state.offered_sell_kWh)
        set_attribute_value_and_test(storage_state.pledged_sell_kWh)
        set_attribute_value_and_test(storage_state.pledged_buy_kWh)
        set_attribute_value_and_test(storage_state.offered_buy_kWh)
