# pylint: disable=protected-access
from unittest.mock import patch

import pytest
from pendulum import now

from gsy_e.models.strategy.state import SmartMeterState
from gsy_e.models.strategy.state.base_states import UnexpectedStateException
from tests.test_state.test_consumption_state import TestConsumptionState
from tests.test_state.test_production_state import TestProductionState


class TestSmartMeterState(TestConsumptionState, TestProductionState):
    """Test PVState class."""

    @staticmethod
    def _setup_base_configuration():
        return SmartMeterState(), now()

    def _setup_default_state(self):
        smart_meter_state, past_time_slot = self._setup_base_configuration()
        current_time_slot = past_time_slot.add(minutes=15)
        smart_meter_state._available_energy_kWh[past_time_slot] = 1
        smart_meter_state._available_energy_kWh[current_time_slot] = 1
        smart_meter_state._desired_energy_Wh[past_time_slot] = 1
        smart_meter_state._desired_energy_Wh[current_time_slot] = 1
        smart_meter_state._energy_production_forecast_kWh[past_time_slot] = 1
        smart_meter_state._energy_production_forecast_kWh[current_time_slot] = 1
        smart_meter_state._energy_requirement_Wh[past_time_slot] = 1
        smart_meter_state._energy_requirement_Wh[current_time_slot] = 1
        return past_time_slot, current_time_slot, smart_meter_state

    def test_delete_past_state_values_market_slot_not_in_past(self):
        past_time_slot, current_time_slot, smart_meter_state = self._setup_default_state()
        with patch("gsy_e.gsy_e_core.util.ConstSettings.SettlementMarketSettings."
                   "ENABLE_SETTLEMENT_MARKETS", True):
            smart_meter_state.delete_past_state_values(current_time_slot)
            assert smart_meter_state.get_available_energy_kWh(
                past_time_slot, default_value=None) is not None
            assert smart_meter_state.get_energy_production_forecast_kWh(
                past_time_slot, default_value=None) is not None
            assert smart_meter_state.get_energy_requirement_Wh(
                past_time_slot, default_value=None) is not None
            assert smart_meter_state.get_desired_energy_Wh(
                past_time_slot, default_value=None) is not None

    def test_delete_past_state_values_market_slot_in_past(self):
        past_time_slot, current_time_slot, smart_meter_state = self._setup_default_state()
        with patch("gsy_e.gsy_e_core.util.ConstSettings.SettlementMarketSettings."
                   "ENABLE_SETTLEMENT_MARKETS", False):
            smart_meter_state.delete_past_state_values(current_time_slot)
            assert smart_meter_state.get_available_energy_kWh(
                past_time_slot) == 0.0
            assert smart_meter_state.get_energy_production_forecast_kWh(
                past_time_slot) == 0.0
            assert smart_meter_state.get_energy_requirement_Wh(
                past_time_slot) == 0.0
            assert smart_meter_state.get_desired_energy_Wh(
                past_time_slot) == 0.0

    def test_get_energy_at_market_slot_production_and_consumption_raise_error(self):
        _, current_time_slot, smart_meter_state = self._setup_default_state()
        smart_meter_state.set_desired_energy(energy=0.0,
                                             time_slot=current_time_slot)
        with pytest.raises(UnexpectedStateException):
            smart_meter_state.get_energy_at_market_slot(time_slot=current_time_slot)
