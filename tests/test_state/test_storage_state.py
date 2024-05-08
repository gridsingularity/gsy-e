# pylint: disable=protected-access, too-many-public-methods
from math import isclose
from unittest.mock import patch, MagicMock, PropertyMock
import pytest
from pendulum import now, duration

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.state import StorageState, ESSEnergyOrigin, EnergyOrigin

SAMPLE_STATE = {
    "pledged_sell_kWh": {},
    "offered_sell_kWh": {},
    "pledged_buy_kWh": {},
    "offered_buy_kWh": {},
    "charge_history": {},
    "charge_history_kWh": {},
    "offered_history": {},
    "energy_to_buy_dict": {},
    "energy_to_sell_dict": {},
    "used_storage": 0.0,
    "battery_energy_per_slot": 0.0,
}

SAMPLE_STATS = {
    "energy_to_sell": 0.0,
    "energy_active_in_bids": 0.0,
    "energy_to_buy": 0.0,
    "energy_active_in_offers": 0.0,
    "free_storage": 0.0,
    "used_storage": 0.0,
}


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
        with patch("gsy_e.models.strategy.state.storage_state.ConstSettings.FutureMarketSettings."
                   "FUTURE_MARKET_DURATION_HOURS", 5):
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
                                     initial_energy_origin=ESSEnergyOrigin.LOCAL,
                                     max_abs_battery_power_kW=15)
        past_time_slot, current_time_slot, future_time_slots = self._initialize_time_slots()
        active_market_slot_time_list = [past_time_slot, current_time_slot, *future_time_slots]
        storage_state.add_default_values_to_state_profiles(active_market_slot_time_list)
        energy = 0.3
        storage_state.activate(
            slot_length=duration(minutes=15), current_time_slot=current_time_slot)
        storage_state.register_energy_from_one_sided_market_accept_offer(
            energy, past_time_slot, ESSEnergyOrigin.LOCAL)
        storage_state.register_energy_from_one_sided_market_accept_offer(
            energy, past_time_slot, ESSEnergyOrigin.UNKNOWN)
        storage_state.register_energy_from_one_sided_market_accept_offer(
            energy, past_time_slot, ESSEnergyOrigin.UNKNOWN)
        storage_state.market_cycle(past_time_slot, current_time_slot, future_time_slots)
        expected_ess_share_last_market = {
            ESSEnergyOrigin.LOCAL: storage_state.initial_capacity_kWh + energy,
            ESSEnergyOrigin.EXTERNAL: 0.0,
            ESSEnergyOrigin.UNKNOWN: 2 * energy
        }
        assert (storage_state.time_series_ess_share[past_time_slot] ==
                expected_ess_share_last_market)

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
        assert (storage_state.charge_history_kWh[current_time_slot] !=
               storage_state.initial_capacity_kWh)
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
        max_value = storage_state.capacity * (1 - storage_state.min_allowed_soc_ratio)
        storage_state.max_abs_battery_power_kW = max_value * 15
        storage_state.activate(
            slot_length=duration(minutes=15), current_time_slot=current_time_slot)

        def set_attribute_value_and_test(attribute):
            attribute[current_time_slot] = -1
            # check that error is raised for value < 0
            with pytest.raises(AssertionError):
                storage_state.check_state(current_time_slot)
            attribute[current_time_slot] = max_value + 1
            # check that error is raised for value > max_value
            with pytest.raises(AssertionError):
                storage_state.check_state(current_time_slot)
            attribute[current_time_slot] = max_value / 2
            # check that for value in range no error is raised
            try:
                storage_state.check_state(current_time_slot)
            except AssertionError as error:
                raise AssertionError from error

        set_attribute_value_and_test(storage_state.offered_sell_kWh)
        set_attribute_value_and_test(storage_state.pledged_sell_kWh)
        set_attribute_value_and_test(storage_state.offered_buy_kWh)
        set_attribute_value_and_test(storage_state.pledged_buy_kWh)

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

    @pytest.mark.parametrize("is_selling", [True, False])
    def test_clamp_energy_asserts_battery_traded_more_than_energy_per_slot(self, is_selling):
        storage_state, market_slot_list = self._setup_storage_state_for_clamp_energy()
        storage_state._battery_energy_per_slot = 0.0
        for time_slot in market_slot_list:
            storage_state.offered_buy_kWh[time_slot] = 5.0
            storage_state.pledged_buy_kWh[time_slot] = 15.0
            storage_state.offered_sell_kWh[time_slot] = 5.0
            storage_state.pledged_sell_kWh[time_slot] = 15.0
        with pytest.raises(AssertionError):
            if is_selling:
                storage_state._clamp_energy_to_sell_kWh(market_slot_list)
            else:
                storage_state._clamp_energy_to_buy_kWh(market_slot_list)

    @staticmethod
    def test_get_state_keys_in_dict():
        storage_state = StorageState()
        current_time_slot = now()
        storage_state.add_default_values_to_state_profiles([current_time_slot])
        assert set(SAMPLE_STATE.keys()).issubset(storage_state.get_state().keys())

    def test_restore_state(self):
        storage_state = StorageState(initial_soc=100,
                                     capacity=100,
                                     min_allowed_soc=20)
        past_time_slot, current_time_slot, future_time_slots = self._initialize_time_slots()
        active_market_slot_time_list = [past_time_slot, current_time_slot, *future_time_slots]
        storage_state.add_default_values_to_state_profiles(active_market_slot_time_list)
        storage_state.activate(
            slot_length=duration(minutes=15), current_time_slot=current_time_slot)
        past_state = storage_state.get_state()
        storage_state.pledged_sell_kWh[current_time_slot] = 50
        modified_state = storage_state.get_state()
        assert past_state != modified_state
        storage_state.restore_state(state_dict=past_state)
        assert storage_state.get_state() == past_state

    @staticmethod
    def test_free_storage_return_float():
        storage_state = StorageState(initial_soc=100,
                                     capacity=100,
                                     min_allowed_soc=20)
        current_time_slot = now()
        storage_state.add_default_values_to_state_profiles([current_time_slot])
        assert isinstance(storage_state.free_storage(current_time_slot), float)

    @staticmethod
    def test_activate_convert_energy_to_power():
        with patch("gsy_e.models.strategy.state.storage_state.convert_kW_to_kWh") as mocked_func:
            storage_state = StorageState()
            current_time_slot = now()
            storage_state.activate(
                slot_length=duration(minutes=15), current_time_slot=current_time_slot)
            mocked_func.assert_called()

    def test_add_default_values_to_state_profiles_set_values_for_time_slots(self):
        storage_state = StorageState()
        _, _, future_time_slots = self._initialize_time_slots()
        storage_state.add_default_values_to_state_profiles(future_time_slots)

        def assert_time_slot_in_dict_attribute_with_default_value(attribute, time_slot, default):
            assert time_slot in attribute.keys()
            assert attribute[time_slot] == default

        for time_slot in future_time_slots:
            assert_time_slot_in_dict_attribute_with_default_value(
                storage_state.pledged_sell_kWh, time_slot, 0)
            assert_time_slot_in_dict_attribute_with_default_value(
                storage_state.pledged_buy_kWh, time_slot, 0)
            assert_time_slot_in_dict_attribute_with_default_value(
                storage_state.offered_sell_kWh, time_slot, 0)
            assert_time_slot_in_dict_attribute_with_default_value(
                storage_state.offered_buy_kWh, time_slot, 0)
            assert_time_slot_in_dict_attribute_with_default_value(
                storage_state.charge_history, time_slot, storage_state.initial_soc)
            assert_time_slot_in_dict_attribute_with_default_value(
                storage_state.charge_history_kWh, time_slot, storage_state.initial_capacity_kWh)
            assert_time_slot_in_dict_attribute_with_default_value(
                storage_state.energy_to_sell_dict, time_slot, 0)
            assert_time_slot_in_dict_attribute_with_default_value(
                storage_state.energy_to_buy_dict, time_slot, 0)
            assert_time_slot_in_dict_attribute_with_default_value(
                storage_state.offered_history, time_slot, "-")
            assert_time_slot_in_dict_attribute_with_default_value(
                storage_state.time_series_ess_share, time_slot, {ESSEnergyOrigin.UNKNOWN: 0.,
                                                                 ESSEnergyOrigin.LOCAL: 0.,
                                                                 ESSEnergyOrigin.EXTERNAL: 0.}
            )

    def test_delete_past_state_values_market_slot_not_in_past(self):
        storage_state = StorageState()
        past_time_slot, current_time_slot, future_time_slots = self._initialize_time_slots()
        active_market_slot_time_list = [past_time_slot, current_time_slot, *future_time_slots]
        storage_state.add_default_values_to_state_profiles(active_market_slot_time_list)
        with patch("gsy_e.gsy_e_core.util.ConstSettings.SettlementMarketSettings."
                   "ENABLE_SETTLEMENT_MARKETS", True):
            storage_state.delete_past_state_values(current_time_slot)
            assert storage_state.pledged_sell_kWh.get(past_time_slot) is not None

    def test_delete_past_state_values_market_slot_in_past(self):
        storage_state = StorageState()
        past_time_slot, current_time_slot, future_time_slots = self._initialize_time_slots()
        active_market_slot_time_list = [past_time_slot, current_time_slot, *future_time_slots]
        storage_state.add_default_values_to_state_profiles(active_market_slot_time_list)
        with patch("gsy_e.gsy_e_core.util.ConstSettings.SettlementMarketSettings."
                   "ENABLE_SETTLEMENT_MARKETS", False):
            storage_state.delete_past_state_values(current_time_slot)
            assert storage_state.pledged_sell_kWh.get(past_time_slot) is None

    def test_register_energy_from_posted_bid_negative_energy_raise_error(self):
        storage_state, current_time_slot = self._setup_registration_test()
        self._assert_negative_energy_raise_error(
            storage_state.register_energy_from_posted_bid, time_slot=current_time_slot)

    def test_register_energy_from_posted_bid_energy_add_energy_to_offered_buy_dict(self):
        storage_state, current_time_slot = self._setup_registration_test()
        bid_energy = 1
        storage_state.register_energy_from_posted_bid(
            energy=bid_energy, time_slot=current_time_slot)
        storage_state.register_energy_from_posted_bid(
            energy=bid_energy, time_slot=current_time_slot)
        assert storage_state.offered_buy_kWh[current_time_slot] == 2 * bid_energy

    def test_register_energy_from_posted_offer_negative_energy_raise_error(self):
        storage_state, current_time_slot = self._setup_registration_test()
        self._assert_negative_energy_raise_error(
            storage_state.register_energy_from_posted_offer,
            time_slot=current_time_slot)

    def test_register_energy_from_posted_offer_energy_add_energy_to_offer_sell_dict(self):
        storage_state, current_time_slot = self._setup_registration_test()
        offered_energy = 1
        storage_state.register_energy_from_posted_offer(
            energy=offered_energy, time_slot=current_time_slot)
        storage_state.register_energy_from_posted_offer(
            energy=offered_energy, time_slot=current_time_slot)
        assert storage_state.offered_sell_kWh[current_time_slot] == 2 * offered_energy

    def test_reset_offered_sell_energy_negative_energy_raise_error(self):
        storage_state, current_time_slot = self._setup_registration_test()
        self._assert_negative_energy_raise_error(
            storage_state.reset_offered_sell_energy, time_slot=current_time_slot)

    def test_reset_offered_sell_energy_energy_in_offered_sell_dict(self):
        storage_state, current_time_slot = self._setup_registration_test()
        offered_sell_energy = 1
        storage_state.reset_offered_sell_energy(
            energy=offered_sell_energy, time_slot=current_time_slot)
        assert storage_state.offered_sell_kWh[current_time_slot] == offered_sell_energy

    def test_reset_offered_buy_energy_negative_energy_raise_error(self):
        storage_state, current_time_slot = self._setup_registration_test()
        self._assert_negative_energy_raise_error(
            storage_state.reset_offered_buy_energy, time_slot=current_time_slot)

    def test_reset_offered_buy_energy_energy_in_offered_buy_dict(self):
        storage_state, current_time_slot = self._setup_registration_test()
        offered_buy_energy = 1
        storage_state.reset_offered_buy_energy(
            energy=offered_buy_energy, time_slot=current_time_slot)
        assert storage_state.offered_buy_kWh[current_time_slot] == offered_buy_energy

    def test_remove_energy_from_deleted_offer_negative_energy_raise_error(self):
        storage_state, current_time_slot = self._setup_registration_test()
        self._assert_negative_energy_raise_error(
            storage_state.remove_energy_from_deleted_offer, time_slot=current_time_slot)

    def test_remove_energy_from_deleted_offer_energy_in_offered_buy_dict(self):
        storage_state, current_time_slot = self._setup_registration_test()
        offered_energy = 1
        storage_state.offered_sell_kWh[current_time_slot] = offered_energy
        storage_state.remove_energy_from_deleted_offer(
            energy=offered_energy, time_slot=current_time_slot)
        assert storage_state.offered_buy_kWh[current_time_slot] == 0

    def test_register_energy_from_one_sided_market_accept_offer_negative_energy_raise_error(self):
        storage_state, current_time_slot = self._setup_registration_test()
        self._assert_negative_energy_raise_error(
            storage_state.register_energy_from_one_sided_market_accept_offer,
            time_slot=current_time_slot)

    def test_register_energy_from_one_sided_market_accept_offer_energy_register_in_dict(self):
        storage_state, current_time_slot = self._setup_registration_test()
        energy = 1
        storage_state.register_energy_from_one_sided_market_accept_offer(
            energy=energy, time_slot=current_time_slot)
        storage_state.register_energy_from_one_sided_market_accept_offer(
            energy=energy, time_slot=current_time_slot)
        assert storage_state.pledged_buy_kWh[current_time_slot] == 2 * energy

    def test_register_energy_from_bid_trade_negative_energy_raise_error(self):
        storage_state, current_time_slot = self._setup_registration_test()
        self._assert_negative_energy_raise_error(
            storage_state.register_energy_from_bid_trade, time_slot=current_time_slot)

    def test_register_energy_from_bid_trade_energy_register_in_dict(self):
        storage_state, current_time_slot = self._setup_registration_test()
        energy = 1
        storage_state.offered_buy_kWh[current_time_slot] = 2 * energy
        storage_state.register_energy_from_bid_trade(
            energy=energy, time_slot=current_time_slot)
        storage_state.register_energy_from_bid_trade(
            energy=energy, time_slot=current_time_slot)
        assert storage_state.pledged_buy_kWh[current_time_slot] == 2 * energy
        assert storage_state.offered_buy_kWh[current_time_slot] == 0

    def test_register_energy_from_offer_trade_negative_energy_raise_error(self):
        storage_state, current_time_slot = self._setup_registration_test()
        self._assert_negative_energy_raise_error(
            storage_state.register_energy_from_offer_trade, time_slot=current_time_slot)

    def test_register_energy_from_offer_trade_energy_register_in_dict(self):
        storage_state, current_time_slot = self._setup_registration_test()
        energy = 1
        storage_state.offered_sell_kWh[current_time_slot] = 2 * energy
        storage_state.register_energy_from_offer_trade(
            energy=energy, time_slot=current_time_slot)
        storage_state.register_energy_from_offer_trade(
            energy=energy, time_slot=current_time_slot)
        assert storage_state.pledged_sell_kWh[current_time_slot] == 2 * energy
        assert storage_state.offered_sell_kWh[current_time_slot] == 0

    def _setup_registration_test(self):
        storage_state = StorageState()
        current_time_slot, _, _ = self._initialize_time_slots()
        storage_state.add_default_values_to_state_profiles([current_time_slot])
        storage_state.activate(
            slot_length=duration(minutes=15), current_time_slot=current_time_slot)
        return storage_state, current_time_slot

    @staticmethod
    def _assert_negative_energy_raise_error(method, time_slot):
        energy = -1
        with pytest.raises(AssertionError):
            method(energy, time_slot)

    @staticmethod
    def _setup_storage_state_for_energy_origin_tracking():
        storage_state = StorageState()
        used_storage_share = [EnergyOrigin(ESSEnergyOrigin.LOCAL, 0.4),
                              EnergyOrigin(ESSEnergyOrigin.EXTERNAL, 0.5),
                              EnergyOrigin(ESSEnergyOrigin.UNKNOWN, 0.1)]
        storage_state._used_storage_share = used_storage_share
        return storage_state

    def test_track_energy_bought_type_append_new_energy_origin_respecting_origin(self):
        storage_state = self._setup_storage_state_for_energy_origin_tracking()
        initial_registry_number = len(storage_state._used_storage_share)
        energy = 1.0
        storage_state._track_energy_bought_type(energy=energy, energy_origin=ESSEnergyOrigin.LOCAL)
        assert len(storage_state._used_storage_share) == initial_registry_number + 1
        assert isinstance(storage_state._used_storage_share[-1], EnergyOrigin)
        assert storage_state._used_storage_share[-1].origin == ESSEnergyOrigin.LOCAL
        assert storage_state._used_storage_share[-1].value == energy

    def test_track_energy_sell_type_sell_all_energy(self):
        storage_state = self._setup_storage_state_for_energy_origin_tracking()
        available_energy_for_sell = 0
        for energy in storage_state._used_storage_share:
            available_energy_for_sell += energy.value
        storage_state._track_energy_sell_type(energy=available_energy_for_sell)
        if len(storage_state._used_storage_share) != 0:
            assert isclose(
                storage_state._used_storage_share[0].value, 0, abs_tol=FLOATING_POINT_TOLERANCE)
        else:
            assert len(storage_state._used_storage_share) == 0

    def test_track_energy_sell_type_sell_more_energy_than_available(self):
        storage_state = self._setup_storage_state_for_energy_origin_tracking()
        available_energy_for_sell = 0
        used_storage_share = storage_state._used_storage_share
        for energy in used_storage_share:
            available_energy_for_sell += energy.value
        storage_state._track_energy_sell_type(energy=available_energy_for_sell + 0.1)
        assert len(storage_state._used_storage_share) == 0

    def test_track_energy_sell_type_sell_only_first_entry_completely(self):
        storage_state = self._setup_storage_state_for_energy_origin_tracking()
        energy_for_sale = 0.4
        initial_registry_number = len(storage_state._used_storage_share)
        original_used_storage_share = storage_state._used_storage_share.copy()
        storage_state._track_energy_sell_type(energy=energy_for_sale)
        assert (len(storage_state._used_storage_share) ==
                initial_registry_number - 1)
        assert (storage_state._used_storage_share[0].origin ==
                original_used_storage_share[1].origin)
        assert isclose(
            storage_state._used_storage_share[0].value,
            original_used_storage_share[1].value,
            abs_tol=FLOATING_POINT_TOLERANCE)

    def test_get_soc_level_default_values_and_custom_values(self):
        storage_state = StorageState(initial_soc=100,
                                     capacity=100)
        current_time_slot, _, _ = self._initialize_time_slots()
        storage_state.add_default_values_to_state_profiles([current_time_slot])
        storage_state.activate(
            slot_length=duration(minutes=15), current_time_slot=current_time_slot)
        assert storage_state.get_soc_level(current_time_slot) == 1
        storage_state.charge_history[current_time_slot] = 50
        assert storage_state.get_soc_level(current_time_slot) == 0.5

    def test_to_dict_keys_in_return_dict(self):
        storage_state = StorageState()
        current_time_slot, _, _ = self._initialize_time_slots()
        storage_state.add_default_values_to_state_profiles([current_time_slot])
        storage_state.energy_to_sell_dict[current_time_slot] = "test_energy_to_sell"
        storage_state.offered_sell_kWh[current_time_slot] = "test_energy_active_in_offers"
        storage_state.energy_to_buy_dict[current_time_slot] = "test_energy_to_buy"
        storage_state.offered_buy_kWh[current_time_slot] = "test_energy_active_in_bids"
        free_storage_mock = MagicMock(return_value="test_free_storage")
        used_storage_mock = PropertyMock()
        storage_state.free_storage = free_storage_mock
        storage_state._used_storage = used_storage_mock

        assert set(SAMPLE_STATS.keys()).issubset(storage_state.to_dict(current_time_slot).keys())
        assert (storage_state.to_dict(current_time_slot)["energy_to_sell"] ==
                "test_energy_to_sell")
        assert (storage_state.to_dict(current_time_slot)["energy_active_in_bids"] ==
                "test_energy_active_in_bids")
        assert (storage_state.to_dict(current_time_slot)["energy_to_buy"] ==
                "test_energy_to_buy")
        assert (storage_state.to_dict(current_time_slot)["energy_active_in_offers"] ==
                "test_energy_active_in_offers")
        assert (storage_state.to_dict(current_time_slot)["free_storage"] ==
                "test_free_storage")
        assert (storage_state.to_dict(current_time_slot)["used_storage"] ==
                used_storage_mock)
