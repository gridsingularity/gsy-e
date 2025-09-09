# pylint: disable=protected-access
from math import isclose
from unittest.mock import Mock

import pytest
from gsy_framework.constants_limits import GlobalConfig, DATE_TIME_FORMAT

from gsy_e.models.strategy.state.heatpump_tank_states.pcm_tank_state import (
    PCMTankState,
    PCMTankParameters,
)

CURRENT_MARKET_SLOT = GlobalConfig.start_date
NEXT_MARKET_SLOT = CURRENT_MARKET_SLOT + GlobalConfig.slot_length


@pytest.fixture(name="pcm_tank")
def fixture_pcm_tank():
    pcm_tank = PCMTankState(
        tank_parameters=PCMTankParameters(
            initial_temp_C=37,
            max_temp_htf_C=42,
            min_temp_htf_C=32,
            max_temp_pcm_C=42,
            min_temp_pcm_C=32,
        )
    )
    pcm_tank._pcm_charge_model.get_soc = Mock(return_value=0.5)
    pcm_tank.init()
    yield pcm_tank


class TestPCMTankState:
    """"""

    def test_increase_tank_temp_from_heat_energy_correctly_updates_storage_temp_and_soc(
        self, pcm_tank
    ):
        # Given
        pcm_tank._get_condenser_temp_from_heat_demand_kWh = Mock(return_value=45)
        pcm_tank._pcm_charge_model.get_temp_after_charging = Mock(
            return_value=([40] * 5, [39] * 5)
        )
        pcm_tank._pcm_charge_model.get_soc = Mock(return_value=0.6)
        assert pcm_tank._soc.get(CURRENT_MARKET_SLOT) == 0.5
        # When
        pcm_tank.increase_tank_temp_from_heat_energy(heat_energy_kWh=1, time_slot=NEXT_MARKET_SLOT)
        # Then
        assert pcm_tank._htf_temps_C[NEXT_MARKET_SLOT] == [40] * 5
        assert pcm_tank._pcm_temps_C[NEXT_MARKET_SLOT] == [39] * 5
        assert pcm_tank._soc.get(NEXT_MARKET_SLOT) == 0.6

    def test_decrease_tank_temp_from_heat_energy_correctly_updates_storage_temp_and_soc(
        self, pcm_tank
    ):
        # Given
        pcm_tank._get_condenser_temp_from_heat_demand_kWh = Mock(return_value=40)
        pcm_tank._pcm_discharge_model.get_temp_after_discharging = Mock(
            return_value=([35] * 5, [36] * 5)
        )
        pcm_tank._pcm_discharge_model.get_soc = Mock(return_value=0.4)
        assert pcm_tank._soc.get(CURRENT_MARKET_SLOT) == 0.5
        # When
        pcm_tank.decrease_tank_temp_from_heat_energy(heat_energy_kWh=1, time_slot=NEXT_MARKET_SLOT)
        # Then
        assert pcm_tank._htf_temps_C[NEXT_MARKET_SLOT] == [35] * 5
        assert pcm_tank._pcm_temps_C[NEXT_MARKET_SLOT] == [36] * 5
        assert pcm_tank._soc.get(NEXT_MARKET_SLOT) == 0.4

    def test_no_charge_correctly_updates_storage_temp_and_soc(self, pcm_tank):
        # Given
        assert pcm_tank._soc.get(CURRENT_MARKET_SLOT) == 0.5
        assert pcm_tank._htf_temps_C.get(CURRENT_MARKET_SLOT) == [37] * 5
        assert pcm_tank._pcm_temps_C.get(CURRENT_MARKET_SLOT) == [37] * 5
        # When
        pcm_tank.no_charge(time_slot=NEXT_MARKET_SLOT)
        # Then
        assert pcm_tank._soc.get(NEXT_MARKET_SLOT) == 0.5
        assert pcm_tank._htf_temps_C.get(CURRENT_MARKET_SLOT) == [37] * 5
        assert pcm_tank._pcm_temps_C.get(CURRENT_MARKET_SLOT) == [37] * 5

    @pytest.mark.parametrize("heat_demand_kJ, expected_energy_kJ", [[5000, 5100], [0, 100]])
    def test_get_max_heat_energy_consumption_kJ_returns_the_correct_energy_value(
        self, pcm_tank, heat_demand_kJ, expected_energy_kJ
    ):
        # When
        pcm_tank.get_dod_energy_kJ = Mock(return_value=100)
        max_energy = pcm_tank.get_max_heat_energy_consumption_kJ(
            CURRENT_MARKET_SLOT, heat_demand_kJ
        )
        # Then
        assert isclose(max_energy, expected_energy_kJ, abs_tol=0.01)

    @pytest.mark.parametrize(
        "current_heat_charge_kJ, expected_energy_kJ",
        [[5100, 0], [5000, 0], [100, 4900], [0, 5000]],
    )
    def test_get_min_heat_energy_consumption_kJ_returns_the_correct_energy_value(
        self, pcm_tank, current_heat_charge_kJ, expected_energy_kJ
    ):
        # Given
        pcm_tank.get_soc_energy_kJ = Mock(return_value=current_heat_charge_kJ)
        # When
        max_energy = pcm_tank.get_min_heat_energy_consumption_kJ(CURRENT_MARKET_SLOT, 5000)
        # Then
        assert isclose(max_energy, expected_energy_kJ, abs_tol=0.1)

    def test_current_tank_temperature(self, pcm_tank):
        assert pcm_tank.current_tank_temperature(CURRENT_MARKET_SLOT) == 37

    def test_init(self):
        # Given
        pcm_tank = PCMTankState(
            tank_parameters=PCMTankParameters(
                initial_temp_C=37,
                max_temp_htf_C=42,
                min_temp_htf_C=32,
                max_temp_pcm_C=42,
                min_temp_pcm_C=32,
            )
        )
        assert pcm_tank._htf_temps_C == {}
        assert pcm_tank._pcm_temps_C == {}
        assert pcm_tank._soc == {}
        pcm_tank._pcm_charge_model.get_soc = Mock(return_value=0.5)
        pcm_tank._pcm_discharge_model.get_soc = Mock(return_value=0.5)
        # When
        pcm_tank.init()
        # Then
        assert pcm_tank._htf_temps_C == {CURRENT_MARKET_SLOT: [37] * 5}
        assert pcm_tank._pcm_temps_C == {CURRENT_MARKET_SLOT: [37] * 5}
        assert pcm_tank._soc == {CURRENT_MARKET_SLOT: 0.5}

    def test_get_htf_temp_C_returns_correct_value(self, pcm_tank):
        pcm_tank._htf_temps_C = {}
        assert pcm_tank.get_htf_temp_C(CURRENT_MARKET_SLOT) is None
        pcm_tank._htf_temps_C = {CURRENT_MARKET_SLOT: [1, 2, 3, 4, 5]}
        assert pcm_tank.get_htf_temp_C(CURRENT_MARKET_SLOT) == 3

    def test_get_pcm_temp_C_returns_correct_value(self, pcm_tank):
        pcm_tank._pcm_temps_C = {}
        assert pcm_tank.get_pcm_temp_C(CURRENT_MARKET_SLOT) is None
        pcm_tank._pcm_temps_C = {CURRENT_MARKET_SLOT: [1, 2, 3, 4, 5]}
        assert pcm_tank.get_pcm_temp_C(CURRENT_MARKET_SLOT) == 3

    def test_get_results_dict_returns_correct_values(self, pcm_tank):
        assert pcm_tank.get_results_dict(CURRENT_MARKET_SLOT) == {
            "soc": 50.0,
            "htf_temp_C": 37,
            "pcm_temp_C": 37,
            "storage_temp_C": 37,
            "type": "PCM",
            "name": "",
            "condenser_temp_C": 37,
        }

    def test_get_state_returns_correct_values(self, pcm_tank):
        assert pcm_tank.get_state() == {
            "htf_temps_C": {CURRENT_MARKET_SLOT.format(DATE_TIME_FORMAT): [37] * 5},
            "pcm_temps_C": {CURRENT_MARKET_SLOT.format(DATE_TIME_FORMAT): [37] * 5},
            "soc": {CURRENT_MARKET_SLOT.format(DATE_TIME_FORMAT): 0.5},
            "condenser_temp_C": {CURRENT_MARKET_SLOT.format(DATE_TIME_FORMAT): 37},
        }

    def test_restore_state_restores_values_correctly(self, pcm_tank):
        pcm_tank.restore_state(
            {
                "htf_temps_C": {CURRENT_MARKET_SLOT.format(DATE_TIME_FORMAT): [50] * 5},
                "pcm_temps_C": {CURRENT_MARKET_SLOT.format(DATE_TIME_FORMAT): [50] * 5},
                "condenser_temp_C": {CURRENT_MARKET_SLOT.format(DATE_TIME_FORMAT): 37},
                "soc": {CURRENT_MARKET_SLOT.format(DATE_TIME_FORMAT): 0.5},
                "min_temp_htf_C": 0,
                "max_temp_htf_C": 100,
                "min_temp_pcm_C": 0,
                "max_temp_pcm_C": 100,
                "initial_temp_C": 50,
            }
        )

        assert pcm_tank._htf_temps_C == {CURRENT_MARKET_SLOT: [50] * 5}
        assert pcm_tank._pcm_temps_C == {CURRENT_MARKET_SLOT: [50] * 5}
        assert pcm_tank._soc == {CURRENT_MARKET_SLOT: 0.5}
        assert pcm_tank._params.min_temp_htf_C == 0.0
        assert pcm_tank._params.max_temp_htf_C == 100
        assert pcm_tank._params.min_temp_pcm_C == 0.0
        assert pcm_tank._params.max_temp_pcm_C == 100
        assert pcm_tank._params.initial_temp_C == 50
        assert pcm_tank._condenser_temp_C == {CURRENT_MARKET_SLOT: 37}
