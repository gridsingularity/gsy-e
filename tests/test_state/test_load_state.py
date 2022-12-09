# pylint: disable=protected-access, arguments-differ
from math import isclose

import pytest
from pendulum import now

from gsy_e.models.strategy.state import LoadState
from tests.test_state.test_consumption_state import TestConsumptionState


class TestLoadState(TestConsumptionState):

    @staticmethod
    def _setup_base_configuration():
        return LoadState(), now()

    def _setup_configuration_for_settlement_posting(
            self, energy_deviation=None, unsettled_deviation=None):
        load_state, current_time_slot = self._setup_base_configuration()
        if energy_deviation:
            load_state._forecast_measurement_deviation_kWh[
                current_time_slot] = energy_deviation
        if unsettled_deviation:
            load_state._unsettled_deviation_kWh[
                current_time_slot] = unsettled_deviation
        return load_state, current_time_slot

    @pytest.mark.parametrize(
        "desired_energy, traded_energy, measured_energy_consumption, expected_deviation",
        [(2000.0, 1000.0, 1.8, 0.8), (2000.0, 2000.0, 1.8, -0.2), (2000.0, 2000.0, 2.0, 0.0)])
    def test_set_energy_measurement_kWh_unsettled_energy_calculation(
            self, desired_energy, traded_energy, measured_energy_consumption, expected_deviation):
        """Test different case scenarios for unsettled energy:
            1st over-consumption,
            2nd under-consumption,
            3rd no unsettled energy.
        """
        load_state, current_time_slot = self._setup_base_configuration()
        load_state.set_desired_energy(
            energy=desired_energy, time_slot=current_time_slot, overwrite=True
        )
        load_state.decrement_energy_requirement(
            purchased_energy_Wh=traded_energy, time_slot=current_time_slot, area_name="TestArea"
        )
        load_state.set_energy_measurement_kWh(
            energy_kWh=measured_energy_consumption, time_slot=current_time_slot
        )
        assert isclose(load_state.get_forecast_measurement_deviation_kWh(
            time_slot=current_time_slot), expected_deviation)
        assert isclose(load_state.get_unsettled_deviation_kWh(
            time_slot=current_time_slot), abs(expected_deviation))
