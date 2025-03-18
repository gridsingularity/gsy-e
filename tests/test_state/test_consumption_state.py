from math import isclose
from unittest.mock import patch
import pytest
from pendulum import now, DateTime

from gsy_framework.constants_limits import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.state.base_states import ConsumptionState, StateInterface
from tests.test_state.test_prosumption_interface import TestProsumptionInterface


class ConsumptionInterfaceHelper(ConsumptionState):
    """Add the get_results_dict abstract method to the ConsumptionState."""

    def get_results_dict(self, current_time_slot: DateTime) -> dict:
        raise NotImplementedError


class TestConsumptionState(TestProsumptionInterface):
    """Test ConsumptionState class."""

    @staticmethod
    def _setup_base_configuration():
        return ConsumptionInterfaceHelper(), now()

    def test_get_state_raise_error_if_conflicting_keys(self):
        with patch.object(StateInterface, "get_state", return_value={"desired_energy_Wh": {-1.0}}):
            consumption_state, _ = self._setup_base_configuration()
            with pytest.raises(AssertionError) as error:
                consumption_state.get_state()
            assert "Conflicting state values found for {'desired_energy_Wh'}." in str(error.value)

    def test_get_state_keys_in_state_dict(self):
        expected_keys = ["desired_energy_Wh", "total_energy_demanded_Wh"]
        consumption_state, _ = self._setup_base_configuration()
        state_dict = consumption_state.get_state()
        assert set(expected_keys).issubset(state_dict.keys())

    def test_restore_state_values_set_properly(self):
        time_slot, consumption_state = self._setup_default_test_consumption_state()
        past_state = consumption_state.get_state()
        consumption_state.set_desired_energy(energy=2.0, time_slot=time_slot)
        consumption_state.update_total_demanded_energy(time_slot=time_slot)
        assert past_state != consumption_state.get_state()
        consumption_state.restore_state(state_dict=past_state)
        assert past_state == consumption_state.get_state()

    def _setup_default_test_consumption_state(self):
        consumption_state, time_slot = self._setup_base_configuration()
        consumption_state.set_desired_energy(energy=1.0, time_slot=time_slot)
        consumption_state.update_total_demanded_energy(time_slot=time_slot)
        return time_slot, consumption_state

    @pytest.mark.parametrize("overwrite, expected_energy", [(True, 2), (False, 1)])
    def test_set_desired_energy_setting_and_overwriting_mechanism(
        self, overwrite, expected_energy
    ):
        time_slot, consumption_state = self._setup_default_test_consumption_state()
        consumption_state.set_desired_energy(energy=2, time_slot=time_slot, overwrite=overwrite)
        assert consumption_state.get_energy_requirement_Wh(time_slot) == expected_energy
        assert consumption_state.get_desired_energy_Wh(time_slot) == expected_energy

    def test_update_total_demanded_energy_respects_addition(self):
        time_slot, consumption_state = self._setup_default_test_consumption_state()
        # Pre-existing time_slot
        initial_demanded_energy = consumption_state.get_state()["total_energy_demanded_Wh"]
        consumption_state.update_total_demanded_energy(time_slot)
        consumption_state.update_total_demanded_energy(time_slot)
        consumption_state.update_total_demanded_energy(time_slot)
        assert (
            consumption_state.get_state()["total_energy_demanded_Wh"]
            == 4 * initial_demanded_energy
        )
        # For non-pre-existing time_slots
        consumption_state.update_total_demanded_energy(time_slot.add(minutes=15))
        assert (
            consumption_state.get_state()["total_energy_demanded_Wh"]
            == 4 * initial_demanded_energy
        )

    def test_can_buy_more_energy_time_slot_not_registered_default_false(self):
        time_slot, consumption_state = self._setup_default_test_consumption_state()
        assert consumption_state.can_buy_more_energy(time_slot=time_slot.add(minutes=15)) is False

    @pytest.mark.parametrize(
        "set_energy, expected_bool", [(1, True), (FLOATING_POINT_TOLERANCE, False)]
    )
    def test_can_buy_more_energy_set_energy_requirement_return_expected(
        self, set_energy, expected_bool
    ):
        time_slot, consumption_state = self._setup_default_test_consumption_state()
        consumption_state.set_desired_energy(
            energy=set_energy, time_slot=time_slot, overwrite=True
        )
        assert consumption_state.can_buy_more_energy(time_slot=time_slot) is expected_bool

    def test_decrement_energy_requirement_respects_subtraction(self):
        time_slot, consumption_state = self._setup_default_test_consumption_state()
        initial_energy_req = consumption_state.get_energy_requirement_Wh(time_slot)
        purchased_energy = 0.3
        consumption_state.decrement_energy_requirement(
            purchased_energy_Wh=purchased_energy, time_slot=time_slot, area_name="test_area"
        )
        consumption_state.decrement_energy_requirement(
            purchased_energy_Wh=purchased_energy, time_slot=time_slot, area_name="test_area"
        )
        assert isclose(
            consumption_state.get_energy_requirement_Wh(time_slot),
            initial_energy_req - 2 * purchased_energy,
        )

    def test_decrement_energy_requirement_purchase_more_than_possible_raise_error(self):
        time_slot, consumption_state = self._setup_default_test_consumption_state()
        purchased_energy = 1.2
        with pytest.raises(AssertionError) as error:
            consumption_state.decrement_energy_requirement(
                purchased_energy_Wh=purchased_energy, time_slot=time_slot, area_name="test_area"
            )
        assert "Energy requirement for device test_area fell below zero " in str(error.value)

    def test_delete_past_state_values_market_slot_not_in_past(self):
        past_time_slot, consumption_state = self._setup_default_test_consumption_state()
        current_time_slot = past_time_slot.add(minutes=15)
        consumption_state.set_desired_energy(energy=1, time_slot=past_time_slot)
        consumption_state.set_desired_energy(energy=1, time_slot=current_time_slot)
        with patch(
            "gsy_e.gsy_e_core.util.ConstSettings.SettlementMarketSettings."
            "ENABLE_SETTLEMENT_MARKETS",
            True,
        ):
            consumption_state.delete_past_state_values(past_time_slot)
            assert consumption_state.get_energy_requirement_Wh(past_time_slot) is not None
            assert consumption_state.get_desired_energy_Wh(past_time_slot) is not None

    def test_delete_past_state_values_market_slot_in_past(self):
        past_time_slot, consumption_state = self._setup_default_test_consumption_state()
        current_time_slot = past_time_slot.add(minutes=15)
        consumption_state.set_desired_energy(energy=1, time_slot=past_time_slot)
        consumption_state.set_desired_energy(energy=1, time_slot=current_time_slot)
        with patch(
            "gsy_e.gsy_e_core.util.ConstSettings.SettlementMarketSettings."
            "ENABLE_SETTLEMENT_MARKETS",
            False,
        ):
            consumption_state.delete_past_state_values(current_time_slot)
            assert (
                consumption_state.get_energy_requirement_Wh(past_time_slot, default_value=100)
                == 100
            )
            assert (
                consumption_state.get_desired_energy_Wh(past_time_slot, default_value=100) == 100
            )
