import pytest
from pendulum import datetime

from d3a.models.state import LoadState, PVState


class TestProsumptionInterface:

    def setup_method(self):
        self.timeslot = datetime(2021, 1, 1, 12, 30)

    @pytest.mark.parametrize("state", [LoadState(), PVState()])
    def test_get_energy_measurement_kWh(self, state):
        state._energy_measurement_kWh[self.timeslot] = 123.0
        assert state.get_energy_measurement_kWh(self.timeslot) == 123

    def test_set_energy_measurement_load(self):
        state = LoadState()
        state._desired_energy_Wh[self.timeslot] = 100000
        state._energy_requirement_Wh[self.timeslot] = 0.0
        state.set_energy_measurement_kWh(234, self.timeslot)
        assert state._energy_measurement_kWh[self.timeslot] == 234.0
        assert state._forecast_measurement_deviation_kWh[self.timeslot] == 134.0
        assert state._unsettled_deviation_kWh[self.timeslot] == 134.0

        state._desired_energy_Wh[self.timeslot] = 250000
        state.set_energy_measurement_kWh(234, self.timeslot)
        assert state._energy_measurement_kWh[self.timeslot] == 234.0
        assert state._forecast_measurement_deviation_kWh[self.timeslot] == -16.0
        assert state._unsettled_deviation_kWh[self.timeslot] == 16.0

    def test_set_energy_measurement_pv(self):
        state = PVState()
        state._energy_production_forecast_kWh[self.timeslot] = 100
        state._available_energy_kWh[self.timeslot] = 0.0
        state.set_energy_measurement_kWh(150, self.timeslot)
        assert state._energy_measurement_kWh[self.timeslot] == 150.0
        assert state._forecast_measurement_deviation_kWh[self.timeslot] == -50.0
        assert state._unsettled_deviation_kWh[self.timeslot] == 50.0

        state.set_energy_measurement_kWh(50, self.timeslot)
        assert state._energy_measurement_kWh[self.timeslot] == 50.0
        assert state._forecast_measurement_deviation_kWh[self.timeslot] == 50.0
        assert state._unsettled_deviation_kWh[self.timeslot] == 50.0

    @pytest.mark.parametrize("state", [LoadState(), PVState()])
    def test_can_post_settlement_bid(self, state):
        state._forecast_measurement_deviation_kWh[self.timeslot] = 123.0
        assert state.can_post_settlement_bid(self.timeslot) is True
        state._forecast_measurement_deviation_kWh[self.timeslot] = -123.0
        assert state.can_post_settlement_bid(self.timeslot) is False
        state._forecast_measurement_deviation_kWh[self.timeslot] = 0.0
        assert state.can_post_settlement_bid(self.timeslot) is False

    @pytest.mark.parametrize("state", [LoadState(), PVState()])
    def test_can_post_settlement_offer(self, state):
        state._forecast_measurement_deviation_kWh[self.timeslot] = -123.0
        assert state.can_post_settlement_offer(self.timeslot) is True
        state._forecast_measurement_deviation_kWh[self.timeslot] = 123.0
        assert state.can_post_settlement_offer(self.timeslot) is False
        state._forecast_measurement_deviation_kWh[self.timeslot] = 0.0
        assert state.can_post_settlement_offer(self.timeslot) is False

    @pytest.mark.parametrize("state", [LoadState(), PVState()])
    def test_decrement_unsettled_deviation(self, state):
        state._unsettled_deviation_kWh[self.timeslot] = 200.0
        state.decrement_unsettled_deviation(100.0, self.timeslot)
        assert state.get_unsettled_deviation_kWh(self.timeslot) == 100.0
        with pytest.raises(AssertionError):
            state.decrement_unsettled_deviation(101.0, self.timeslot)

    @pytest.mark.parametrize("state", [LoadState(), PVState()])
    def test_get_forecast_measurement_deviation(self, state):
        state._forecast_measurement_deviation_kWh[self.timeslot] = 100.0
        assert state.get_forecast_measurement_deviation_kWh(self.timeslot) == 100

    @pytest.mark.parametrize("state", [LoadState(), PVState()])
    def test_get_unsettled_deviation(self, state):
        state._unsettled_deviation_kWh[self.timeslot] = 300.0
        assert state.get_unsettled_deviation_kWh(self.timeslot) == 300
