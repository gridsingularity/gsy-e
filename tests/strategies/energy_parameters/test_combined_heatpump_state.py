# pylint: disable = protected-access
from math import isclose
from unittest.mock import Mock, patch

import pytest
from gsy_framework.constants_limits import GlobalConfig
from gsy_framework.utils import convert_kWh_to_kW

from gsy_e.models.strategy.energy_parameters.heatpump.cop_models import UniversalCOPModel
from gsy_e.models.strategy.energy_parameters.heatpump.heat_pump import CombinedHeatpumpTanksState

CURRENT_MARKET_SLOT = GlobalConfig.start_date
LAST_MARKET_SLOT = CURRENT_MARKET_SLOT - GlobalConfig.slot_length


@pytest.fixture(name="combined_state")
def fixture_combined_state():
    combined_state = CombinedHeatpumpTanksState(
        hp_state=Mock(),
        tanks_state=Mock(),
        cop_model=Mock(),
        max_energy_consumption_kWh=5,
    )

    yield combined_state


class TestCombinedHeatpumpTanksState:

    def test_get_energy_to_buy_maximum_kWh_calls_correct_methods(self, combined_state):
        # Given
        combined_state.heatpump.get_heat_demand_kJ = Mock(return_value=5000)
        combined_state._charger.get_max_heat_energy_charge_kJ = Mock(return_value=1800)
        combined_state._charger.get_average_inlet_temperature_C = Mock(return_value=30)
        combined_state._cop_model.calc_cop = Mock(return_value=4)
        # When
        ret_value = combined_state.get_energy_to_buy_maximum_kWh(CURRENT_MARKET_SLOT, 20)
        # Then
        assert isclose(ret_value, 0.125, abs_tol=0.001)
        combined_state._charger.get_max_heat_energy_charge_kJ.assert_called_with(
            CURRENT_MARKET_SLOT, 5000
        )
        combined_state._cop_model.calc_cop.assert_called_with(
            source_temp_C=20, condenser_temp_C=30, heat_demand_kW=2.0
        )

    def test_get_energy_to_buy_maximum_kWh_limits_cop_to_global_setting(self, combined_state):
        # Given
        combined_state.heatpump.get_heat_demand_kJ = Mock(return_value=5000)
        combined_state._charger.get_max_heat_energy_charge_kJ = Mock(return_value=1800)
        combined_state._charger.get_average_tank_temp_C = Mock(return_value=30)
        combined_state._cop_model.calc_cop = Mock(return_value=2)
        # When
        with patch("gsy_e.constants.HP_MIN_COP", 3):
            ret_value = combined_state.get_energy_to_buy_maximum_kWh(CURRENT_MARKET_SLOT, 20)
        # Then
        assert isclose(ret_value, 0.166, abs_tol=0.001)

    def test_get_energy_to_buy_minimum_kWh_calls_correct_methods(self, combined_state):
        # Given
        combined_state.heatpump.get_heat_demand_kJ = Mock(return_value=5000)
        combined_state._charger.get_min_heat_energy_charge_kJ = Mock(return_value=1800)
        combined_state._charger.get_average_inlet_temperature_C = Mock(return_value=30)
        combined_state._cop_model.calc_cop = Mock(return_value=4)
        # When
        ret_value = combined_state.get_energy_to_buy_minimum_kWh(CURRENT_MARKET_SLOT, 20)
        # Then
        assert isclose(ret_value, 0.125, abs_tol=0.001)
        combined_state._charger.get_min_heat_energy_charge_kJ.assert_called_with(
            CURRENT_MARKET_SLOT, 5000
        )
        combined_state._cop_model.calc_cop.assert_called_with(
            source_temp_C=20, condenser_temp_C=30, heat_demand_kW=2.0
        )

    @pytest.mark.parametrize(
        "bought_energy_kWh, expected_command",
        [[2, "charge"], [1, "no_charge"], [0.5, "discharge"]],
    )
    def test_update_tanks_temperature_calls_correct_methods(
        self, combined_state, bought_energy_kWh, expected_command
    ):
        # Given
        combined_state._charger.charge = Mock()
        combined_state._charger.no_charge = Mock()
        combined_state._charger.discharge = Mock()
        combined_state.calc_Q_kJ_from_energy_kWh = Mock(return_value=bought_energy_kWh * 5000)
        # When
        combined_state.update_tanks_temperature(
            LAST_MARKET_SLOT, CURRENT_MARKET_SLOT, bought_energy_kWh, 5000, 20
        )
        # Then
        called = False
        if expected_command == "charge":
            called = True
            combined_state._charger.charge.assert_called_once()
        if expected_command == "no_charge":
            called = True
            combined_state._charger.no_charge.assert_called_once()
        if expected_command == "discharge":
            called = True
            combined_state._charger.discharge.assert_called_once()
        assert called, "one of the methods should have been called"

    @staticmethod
    def test_delete_past_state_values_triggers_deletion_in_states(combined_state):
        combined_state._hp_state.delete_past_state_values = Mock()
        combined_state._charger.delete_past_state_values = Mock()

        combined_state.delete_past_state_values(CURRENT_MARKET_SLOT)

        combined_state._hp_state.delete_past_state_values.assert_called_once()
        combined_state._charger.delete_past_state_values.assert_called_once()

    def test_update_cop_after_dis_charging_universal_cop_model_sets_cop_on_both_slots(self):
        # Given
        cop_model = Mock(spec=UniversalCOPModel)
        cop_model.calc_cop.return_value = 3.5
        combined_state = CombinedHeatpumpTanksState(
            hp_state=Mock(),
            tanks_state=Mock(),
            cop_model=cop_model,
            max_energy_consumption_kWh=5,
        )
        combined_state._charger.get_average_inlet_temperature_C = Mock(return_value=40)
        # When
        combined_state.update_cop_after_dis_charging(
            source_temp_C=10,
            time_slot=CURRENT_MARKET_SLOT,
            last_time_slot=LAST_MARKET_SLOT,
            bought_energy_kWh=1.0,
        )
        # Then
        cop_model.calc_cop.assert_called_once_with(source_temp_C=10, condenser_temp_C=40)
        combined_state._hp_state.set_cop.assert_any_call(LAST_MARKET_SLOT, 3.5)
        combined_state._hp_state.set_cop.assert_any_call(CURRENT_MARKET_SLOT, 3.5)

    def test_update_cop_after_dis_charging_zero_energy_sets_only_current_slot_cop(
        self, combined_state
    ):
        # Given
        combined_state._hp_state.get_cop.return_value = 2.5
        # When
        combined_state.update_cop_after_dis_charging(
            source_temp_C=10,
            time_slot=CURRENT_MARKET_SLOT,
            last_time_slot=LAST_MARKET_SLOT,
            bought_energy_kWh=0.0,
        )
        # Then
        combined_state._hp_state.get_cop.assert_called_once_with(LAST_MARKET_SLOT)
        combined_state._hp_state.set_cop.assert_called_once_with(CURRENT_MARKET_SLOT, 2.5)

    def test_update_cop_after_dis_charging_valid_heat_energy_calculates_correct_cop(
        self, combined_state
    ):
        # Given
        heat_energy_kW = 8.0
        bought_energy_kWh = 1.0
        combined_state._charger.get_average_inlet_temperature_C = Mock(return_value=40)
        combined_state._cop_model.calc_q_from_p_kW.return_value = heat_energy_kW
        # When
        combined_state.update_cop_after_dis_charging(
            source_temp_C=10,
            time_slot=CURRENT_MARKET_SLOT,
            last_time_slot=LAST_MARKET_SLOT,
            bought_energy_kWh=bought_energy_kWh,
        )
        # Then
        bought_energy_kW = convert_kWh_to_kW(bought_energy_kWh, GlobalConfig.slot_length)
        expected_cop = heat_energy_kW / bought_energy_kW
        combined_state._hp_state.set_cop.assert_any_call(LAST_MARKET_SLOT, expected_cop)
        combined_state._hp_state.set_cop.assert_any_call(CURRENT_MARKET_SLOT, expected_cop)

    def test_update_cop_after_dis_charging_none_heat_energy_uses_last_slot_cop(
        self, combined_state
    ):
        # Given
        combined_state._charger.get_average_inlet_temperature_C = Mock(return_value=40)
        combined_state._cop_model.calc_q_from_p_kW.return_value = None
        combined_state._hp_state.get_cop.return_value = 2.8
        # When
        combined_state.update_cop_after_dis_charging(
            source_temp_C=10,
            time_slot=CURRENT_MARKET_SLOT,
            last_time_slot=LAST_MARKET_SLOT,
            bought_energy_kWh=1.0,
        )
        # Then
        combined_state._hp_state.get_cop.assert_called_once_with(LAST_MARKET_SLOT)
        combined_state._hp_state.set_cop.assert_any_call(LAST_MARKET_SLOT, 2.8)
        combined_state._hp_state.set_cop.assert_any_call(CURRENT_MARKET_SLOT, 2.8)
