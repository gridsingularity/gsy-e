# pylint: disable=protected-access
from pendulum import now

from gsy_e.models.state import PVState
from tests.test_state.test_prosumption_interface import TestProsumptionInterface


class TestPVState(TestProsumptionInterface):

    @staticmethod
    def _setup_base_configuration():
        return PVState(), now()

    @staticmethod
    def _setup_configuration_for_settlement_posting(
            energy_deviation=None, unsettled_deviation=None):
        pv_state = PVState()
        current_time_slot = now()
        if energy_deviation:
            pv_state._forecast_measurement_deviation_kWh[
                current_time_slot] = energy_deviation
        if unsettled_deviation:
            pv_state._unsettled_deviation_kWh[
                current_time_slot] = unsettled_deviation
        return pv_state, current_time_slot
