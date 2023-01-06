# pylint: disable=protected-access, arguments-differ
from math import isclose

import pytest
from pendulum import now

from gsy_e.models.strategy.state import PVState
from tests.test_state.test_production_state import TestProductionState


class TestPVState(TestProductionState):

    @staticmethod
    def _setup_base_configuration():
        return PVState(), now()

    def _setup_configuration_for_settlement_posting(
            self, energy_deviation=None, unsettled_deviation=None):
        pv_state, current_time_slot = self._setup_base_configuration()
        if energy_deviation:
            pv_state._forecast_measurement_deviation_kWh[
                current_time_slot] = energy_deviation
        if unsettled_deviation:
            pv_state._unsettled_deviation_kWh[
                current_time_slot] = unsettled_deviation
        return pv_state, current_time_slot

    @pytest.mark.parametrize(
        "forecasted_energy_production, traded_energy, "
        "measured_energy_production, expected_deviation",
        [(2.0, 1.0, 1.8, -0.8), (2.0, 2.0, 1.8, 0.2), (2.0, 2.0, 2.0, 0.0)])
    def test_set_energy_measurement_kWh_unsettled_energy_calculation(
            self, forecasted_energy_production, traded_energy,
            measured_energy_production, expected_deviation):
        """Test different case scenarios for unsettled energy:
            1st overproduction,
            2nd underproduction,
            3rd no unsettled energy.
        """
        pv_state, current_time_slot = self._setup_base_configuration()
        pv_state.set_available_energy(
            energy_kWh=forecasted_energy_production, time_slot=current_time_slot, overwrite=True
        )
        pv_state.decrement_available_energy(
            sold_energy_kWh=traded_energy, time_slot=current_time_slot, area_name="TestArea"
        )
        pv_state.set_energy_measurement_kWh(
            energy_kWh=measured_energy_production, time_slot=current_time_slot
        )
        assert isclose(pv_state.get_forecast_measurement_deviation_kWh(
            time_slot=current_time_slot), expected_deviation)
        assert isclose(pv_state.get_unsettled_deviation_kWh(
            time_slot=current_time_slot), abs(expected_deviation))
