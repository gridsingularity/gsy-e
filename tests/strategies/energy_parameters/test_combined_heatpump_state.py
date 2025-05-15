# pylint: disable = protected-access
from math import isclose
from unittest.mock import Mock

import pytest
from gsy_framework.constants_limits import GlobalConfig

from gsy_e.models.strategy.energy_parameters.heatpump.heat_pump import CombinedHeatpumpTanksState
from gsy_e.models.strategy.strategy_profile import profile_factory

CURRENT_MARKET_SLOT = GlobalConfig.start_date
LAST_MARKET_SLOT = CURRENT_MARKET_SLOT - GlobalConfig.slot_length


@pytest.fixture(name="combined_state")
def fixture_combined_state():
    combined_state = CombinedHeatpumpTanksState(
        hp_state=Mock(),
        tanks_state=Mock(),
        cop_model=Mock(),
        slot_length=GlobalConfig.slot_length,
        max_energy_consumption_kWh=5,
    )

    yield combined_state


class TestCombinedHeatpumpTanksState:

    def test_get_energy_to_buy_maximum_kWh_calls_correct_methods(self, combined_state):
        # Given
        combined_state.heatpump.get_heat_demand_kJ = Mock(return_value=5000)
        combined_state.charger.get_max_heat_energy_charge_kJ = Mock(return_value=1800)
        combined_state.charger.get_condenser_temperature_C = Mock(return_value=30)
        combined_state._cop_model.calc_cop = Mock(return_value=4)
        # When
        ret_value = combined_state.get_energy_to_buy_maximum_kWh(CURRENT_MARKET_SLOT, 20)
        # Then
        assert isclose(ret_value, 0.125, abs_tol=0.001)
        combined_state.charger.get_max_heat_energy_charge_kJ.assert_called_with(
            CURRENT_MARKET_SLOT, 5000
        )
        combined_state._cop_model.calc_cop.assert_called_with(
            source_temp_C=20, condenser_temp_C=30, heat_demand_kW=2.0
        )

    def test_get_energy_to_buy_minimum_kWh_calls_correct_methods(self, combined_state):
        # Given
        combined_state.heatpump.get_heat_demand_kJ = Mock(return_value=5000)
        combined_state.charger.get_min_heat_energy_charge_kJ = Mock(return_value=1800)
        combined_state.charger.get_condenser_temperature_C = Mock(return_value=30)
        combined_state._cop_model.calc_cop = Mock(return_value=4)
        # When
        ret_value = combined_state.get_energy_to_buy_minimum_kWh(CURRENT_MARKET_SLOT, 20)
        # Then
        assert isclose(ret_value, 0.125, abs_tol=0.001)
        combined_state.charger.get_min_heat_energy_charge_kJ.assert_called_with(
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
        combined_state.charger.charge = Mock()
        combined_state.charger.no_charge = Mock()
        combined_state.charger.discharge = Mock()
        combined_state.calc_Q_kJ_from_energy_kWh = Mock(return_value=bought_energy_kWh * 5000)
        # When
        combined_state.update_tanks_temperature(
            LAST_MARKET_SLOT, CURRENT_MARKET_SLOT, bought_energy_kWh, 5000, 20
        )
        # Then
        called = False
        if expected_command == "charge":
            called = True
            combined_state.charger.charge.assert_called_once()
        if expected_command == "no_charge":
            called = True
            combined_state.charger.no_charge.assert_called_once()
        if expected_command == "discharge":
            called = True
            combined_state.charger.discharge.assert_called_once()
        assert called, "one of the methods should have been called"

    @pytest.mark.parametrize("ancillary_heat_source", [True, False])
    def test_get_net_heat_demand_kJ_returns_correct_values(
        self, combined_state, ancillary_heat_source
    ):
        # Given
        combined_state.heatpump.get_heat_demand_kJ = Mock(return_value=5000)
        if ancillary_heat_source:
            combined_state._ancillary_heat_source_kJ = profile_factory(
                input_profile={CURRENT_MARKET_SLOT: 6000}
            )
            combined_state.rotate_profiles()
        # When
        ret_val = combined_state.get_net_heat_demand_kJ(CURRENT_MARKET_SLOT)
        # Then
        if ancillary_heat_source:
            assert ret_val == -1000
        else:
            assert ret_val == 5000

    @pytest.mark.parametrize("ancillary_heat_source_kJ", [0, 3000, 6000])
    def test__get_heat_demand_kJ_returns_correct_values(
        self, combined_state, ancillary_heat_source_kJ
    ):
        # Given
        combined_state.heatpump.get_heat_demand_kJ = Mock(return_value=5000)
        combined_state._ancillary_heat_source_kJ = profile_factory(
            input_profile={CURRENT_MARKET_SLOT: ancillary_heat_source_kJ}
        )
        combined_state.rotate_profiles()
        # When
        ret_val = combined_state._get_heat_demand_kJ(CURRENT_MARKET_SLOT)
        # Then
        assert ret_val == max(5000 - ancillary_heat_source_kJ, 0)
