# pylint: disable=protected-access
from math import isclose
from unittest.mock import patch
import pytest
from pendulum import now, DateTime

from gsy_e.models.strategy.state.base_states import ProductionState, StateInterface
from tests.test_state.test_prosumption_interface import TestProsumptionInterface


class ProductionInterfaceHelper(ProductionState):
    """Add the get_results_dict abstract method to the ProductionState."""

    def get_results_dict(self, current_time_slot: DateTime) -> dict:
        raise NotImplementedError


class TestProductionState(TestProsumptionInterface):
    """Test ProductionState class."""

    @staticmethod
    def _setup_base_configuration():
        return ProductionInterfaceHelper(), now()

    def test_get_state_raise_error_if_conflicting_keys(self):
        with patch.object(StateInterface, "get_state",
                          return_value={"available_energy_kWh": {-1.0}}):
            production_state, _ = self._setup_base_configuration()
            with pytest.raises(AssertionError) as error:
                production_state.get_state()
            assert ("Conflicting state values found for {'available_energy_kWh'}."
                    in str(error.value))

    def test_get_state_keys_in_state_dict(self):
        expected_keys = ["available_energy_kWh",
                         "energy_production_forecast_kWh"]
        production_state, _ = self._setup_base_configuration()
        state_dict = production_state.get_state()
        assert set(expected_keys).issubset(state_dict.keys())

    def test_restore_state_values_set_properly(self):
        time_slot, production_state = self._setup_default_test_production_state()
        past_state = production_state.get_state()
        production_state.set_available_energy(
            energy_kWh=2.0,
            time_slot=time_slot,
            overwrite=True
        )
        assert past_state != production_state.get_state()
        production_state.restore_state(state_dict=past_state)
        assert past_state == production_state.get_state()

    def _setup_default_test_production_state(self):
        production_state, time_slot = self._setup_base_configuration()
        production_state.set_available_energy(
            energy_kWh=1.0,
            time_slot=time_slot
        )
        return time_slot, production_state

    @pytest.mark.parametrize("overwrite, expected_energy", [(True, 2), (False, 1)])
    def test_set_available_energy_setting_and_overwriting_mechanism(
            self, overwrite, expected_energy):
        time_slot, production_state = self._setup_default_test_production_state()
        production_state.set_available_energy(energy_kWh=2,
                                              time_slot=time_slot,
                                              overwrite=overwrite)
        assert production_state.get_available_energy_kWh(
            time_slot) == expected_energy
        assert production_state.get_energy_production_forecast_kWh(
            time_slot) == expected_energy

    def test_get_available_energy_kWh_negative_energy_raise_error(self):
        time_slot, production_state = self._setup_default_test_production_state()
        production_state._available_energy_kWh[time_slot] = -1
        with pytest.raises(AssertionError):
            production_state.get_available_energy_kWh(time_slot)

    def test_decrement_available_energy_respects_subtraction(self):
        time_slot, production_state = self._setup_default_test_production_state()
        initial_available_energy = production_state.get_available_energy_kWh(time_slot)
        sold_energy = 0.3
        production_state.decrement_available_energy(sold_energy_kWh=sold_energy,
                                                    time_slot=time_slot,
                                                    area_name="test_area")
        production_state.decrement_available_energy(sold_energy_kWh=sold_energy,
                                                    time_slot=time_slot,
                                                    area_name="test_area")
        assert isclose(
            production_state.get_available_energy_kWh(time_slot),
            initial_available_energy - 2 * sold_energy
        )

    def test_decrement_energy_requirement_sell_more_than_possible_raise_error(self):
        time_slot, production_state = self._setup_default_test_production_state()
        sold_energy = 1.2
        with pytest.raises(AssertionError) as error:
            production_state.decrement_available_energy(sold_energy_kWh=sold_energy,
                                                        time_slot=time_slot,
                                                        area_name="test_area")
        assert ("Available energy for device test_area fell below zero "
                ) in str(error.value)

    def test_delete_past_state_values_market_slot_not_in_past(self):
        past_time_slot, production_state = self._setup_default_test_production_state()
        current_time_slot = past_time_slot.add(minutes=15)
        production_state.set_available_energy(energy_kWh=1, time_slot=past_time_slot)
        production_state.set_available_energy(energy_kWh=1, time_slot=current_time_slot)
        with patch("gsy_e.gsy_e_core.util.ConstSettings.SettlementMarketSettings."
                   "ENABLE_SETTLEMENT_MARKETS", True):
            production_state.delete_past_state_values(past_time_slot)
            assert production_state.get_energy_production_forecast_kWh(past_time_slot) is not None
            assert production_state.get_available_energy_kWh(past_time_slot) is not None

    def test_delete_past_state_values_market_slot_in_past(self):
        past_time_slot, production_state = self._setup_default_test_production_state()
        current_time_slot = past_time_slot.add(minutes=15)
        production_state.set_available_energy(energy_kWh=1, time_slot=past_time_slot)
        production_state.set_available_energy(energy_kWh=1, time_slot=current_time_slot)
        with patch("gsy_e.gsy_e_core.util.ConstSettings.SettlementMarketSettings."
                   "ENABLE_SETTLEMENT_MARKETS", False):
            production_state.delete_past_state_values(current_time_slot)
            assert production_state.get_energy_production_forecast_kWh(past_time_slot,
                                                                       default_value=100) == 100
            assert production_state.get_available_energy_kWh(past_time_slot,
                                                             default_value=100) == 100

    def test_get_energy_production_forecast_kWh_negative_energy_raise_error(self):
        time_slot, production_state = self._setup_default_test_production_state()
        production_state._energy_production_forecast_kWh[time_slot] = -1
        with pytest.raises(AssertionError):
            production_state.get_energy_production_forecast_kWh(time_slot)
