from math import isclose

from deepdiff import DeepDiff
from pendulum import datetime

from gsy_framework.constants_limits import GlobalConfig

from gsy_e.models.strategy.energy_parameters.heatpump.tank_parameters import TankParameters
from gsy_e.models.strategy.state.heatpump_tank_states.all_tanks_state import AllTanksState

from gsy_e.models.strategy.energy_parameters.heatpump.virtual_heatpump_tank import (
    VirtualHeatpumpAllTanksState,
    VirtualHeatpumpSolverParameters,
)


# pylint: disable=attribute-defined-outside-init,protected-access
class TestAllTanksState:

    def setup_method(self):
        self._tanks = AllTanksState(
            [
                TankParameters(10, 50, 25, 500),
                TankParameters(20, 40, 20, 800),
                TankParameters(30, 60, 60, 1000),
            ]
        )
        self._datetime = datetime(2023, 1, 1, 0, 0)
        for tank in self._tanks.tanks_states:
            tank._update_soc(self._datetime)
            tank._update_soc(self._datetime - GlobalConfig.slot_length)

    def test_increase_tanks_temp_from_heat_energy_updates_tank_temperature_correctly(self):
        self._tanks.increase_tanks_temp_from_heat_energy(5000, self._datetime)
        tank_states = self._tanks.tanks_states
        assert isclose(tank_states[0]._storage_temp_C[self._datetime], 26.050, rel_tol=0.0001)
        assert isclose(tank_states[1]._storage_temp_C[self._datetime], 20.840, rel_tol=0.0001)
        assert isclose(tank_states[2]._storage_temp_C[self._datetime], 60, rel_tol=0.0001)

    def test_decrease_tanks_temp_from_heat_energy_updates_tank_temperature_correctly(self):

        self._tanks.decrease_tanks_temp_from_heat_energy(5000, self._datetime)
        tank_states = self._tanks.tanks_states
        assert isclose(tank_states[0]._storage_temp_C[self._datetime], 24.521, rel_tol=0.0001)
        assert isclose(tank_states[1]._storage_temp_C[self._datetime], 20.0, rel_tol=0.0001)
        assert isclose(tank_states[2]._storage_temp_C[self._datetime], 59.0421, rel_tol=0.0001)

    def test_get_max_energy_consumption(self):
        max_energy_consumption = self._tanks.get_max_heat_energy_consumption_kJ(
            self._datetime, 1000
        )
        assert isclose(max_energy_consumption, 120016, rel_tol=0.0001)

    def test_get_min_energy_consumption(self):
        min_energy_consumption = self._tanks.get_min_heat_energy_consumption_kJ(
            self._datetime, 200000
        )
        assert isclose(min_energy_consumption, 43400, rel_tol=0.1)

    def test_get_average_tank_temperature(self):
        self._tanks.tanks_states[0]._storage_temp_C[self._datetime] = 30
        self._tanks.tanks_states[1]._storage_temp_C[self._datetime] = 35
        self._tanks.tanks_states[2]._storage_temp_C[self._datetime] = 40
        assert self._tanks.get_average_tank_temperature(self._datetime) == 35

    def test_serialize(self):
        tanks_dict = self._tanks.serialize()
        expected_dict = [
            {"max_temp_C": 50, "min_temp_C": 10, "tank_volume_l": 500},
            {"max_temp_C": 40, "min_temp_C": 20, "tank_volume_l": 800},
            {"max_temp_C": 60, "min_temp_C": 30, "tank_volume_l": 1000},
        ]

        assert len(DeepDiff(tanks_dict, expected_dict)) == 0

    def test_get_results_dict(self):
        results_dict = self._tanks.get_results_dict(self._datetime)
        expected_dict = [
            {"storage_temp_C": 25, "soc": 37.5},
            {"storage_temp_C": 20, "soc": 0.0},
            {"storage_temp_C": 60, "soc": 100.0},
        ]
        assert len(DeepDiff(results_dict, expected_dict)) == 0


class TestVirtualHeatpumpAllTanksEnergyParameters:

    def setup_method(self):
        self._tanks = VirtualHeatpumpAllTanksState(
            [
                TankParameters(10, 50, 25, 500),
                TankParameters(20, 40, 20, 800),
                TankParameters(30, 60, 60, 1000),
            ]
        )
        self._datetime = datetime(2023, 1, 1, 0, 0)

    def test_set_temp_decrease_vhp_works_with_one_tank_empty(self):
        self._tanks.set_temp_decrease_vhp(1000, self._datetime)

        energy_params = self._tanks.tanks_states
        assert isclose(energy_params[0]._temp_decrease_K[self._datetime], 0.14347, rel_tol=0.0001)
        assert isclose(energy_params[1]._temp_decrease_K[self._datetime], 0.0, rel_tol=0.0001)
        assert isclose(energy_params[2]._temp_decrease_K[self._datetime], 0.07174, rel_tol=0.0001)

    def test_set_temp_decrease_vhp_all_tanks(self):
        self._tanks.tanks_states[1]._storage_temp_C[self._datetime] = 30.0
        solver_params = self._tanks.set_temp_decrease_vhp(1000, self._datetime)
        assert not solver_params
        energy_params = self._tanks.tanks_states
        assert isclose(energy_params[0]._temp_decrease_K[self._datetime], 0.14347, rel_tol=0.0001)
        assert isclose(energy_params[1]._temp_decrease_K[self._datetime], 0.08967, rel_tol=0.0001)
        assert isclose(energy_params[2]._temp_decrease_K[self._datetime], 0.07174, rel_tol=0.0001)

    def test_create_tank_solver_for_maintaining_tank_temperature(self):
        solver_params = self._tanks.create_tank_solver_for_maintaining_tank_temperature(
            self._datetime
        )
        assert solver_params[0].tank_volume_L == 500
        assert solver_params[0].current_storage_temp_C == 25
        assert solver_params[0].target_storage_temp_C == 25
        assert solver_params[1].tank_volume_L == 800
        assert solver_params[1].current_storage_temp_C == 20
        assert solver_params[1].target_storage_temp_C == 20
        assert solver_params[2].tank_volume_L == 1000
        assert solver_params[2].current_storage_temp_C == 60
        assert solver_params[2].target_storage_temp_C == 60

    def test_create_tank_parameters_for_maxing_tank_temperature(self):
        solver_params = self._tanks.create_tank_parameters_for_maxing_tank_temperature(
            self._datetime
        )
        assert solver_params[0].tank_volume_L == 500
        assert solver_params[0].current_storage_temp_C == 25
        assert solver_params[0].target_storage_temp_C == 50
        assert solver_params[1].tank_volume_L == 800
        assert solver_params[1].current_storage_temp_C == 20
        assert solver_params[1].target_storage_temp_C == 40
        assert solver_params[2].tank_volume_L == 1000
        assert solver_params[2].current_storage_temp_C == 60
        assert solver_params[2].target_storage_temp_C == 60

    def test_increase_tanks_temperature_with_energy_vhp(self):
        solver_params = VirtualHeatpumpSolverParameters(
            dh_supply_temp_C=60,
            dh_return_temp_C=45,
            dh_flow_m3_per_hour=0.1,
            source_temp_C=12,
            calibration_coefficient=0.85,
            energy_kWh=10.0,
        )
        self._tanks.increase_tanks_temperature_with_energy_vhp(solver_params, self._datetime)
        # Temp increase is shared equally across tanks
        for energy_param in self._tanks.tanks_states:
            assert isclose(energy_param.get_temp_increase_K(self._datetime), 3.306, rel_tol=0.0001)
