# pylint: disable=protected-access

import pytest
from gsy_framework.constants_limits import GlobalConfig, TIME_ZONE
from pendulum import duration, today

from gsy_e.models.strategy.energy_parameters.heat_pump import HeatPumpEnergyParameters

CURRENT_MARKET_SLOT = today(tz=TIME_ZONE)


@pytest.fixture(name="energy_params")
def fixture_heatpump_energy_params() -> HeatPumpEnergyParameters:
    original_start_date = GlobalConfig.start_date
    original_sim_duration = GlobalConfig.sim_duration
    original_slot_length = GlobalConfig.slot_length
    GlobalConfig.start_date = CURRENT_MARKET_SLOT
    GlobalConfig.sim_duration = duration(days=1)
    GlobalConfig.slot_length = duration(minutes=60)
    yield HeatPumpEnergyParameters()
    GlobalConfig.start_date = original_start_date
    GlobalConfig.sim_duration = original_sim_duration
    GlobalConfig.slot_length = original_slot_length


class TestHeatPumpEnergyParameters:

    @staticmethod
    def test_event_activates_populates_profiles(energy_params):
        energy_params.event_activate()
        assert len(energy_params._consumption_kWh.profile) == 24
        assert len(energy_params._ext_temp_C.profile) == 24

    @staticmethod
    def test_event_market_cycle_populates_profiles(energy_params):
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        assert len(energy_params._consumption_kWh.profile) == 24
        assert len(energy_params._ext_temp_C.profile) == 24

    @staticmethod
    def test_event_market_cycle_populates_state(energy_params):
        assert CURRENT_MARKET_SLOT not in energy_params.state._temp_decrease_K
        assert CURRENT_MARKET_SLOT not in energy_params.state._storage_temp_C
        assert CURRENT_MARKET_SLOT not in energy_params.state._min_energy_demand_kWh
        assert CURRENT_MARKET_SLOT not in energy_params.state._max_energy_demand_kWh
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        assert energy_params.state._temp_decrease_K[CURRENT_MARKET_SLOT] == 0.28275862068965524
        assert energy_params.state._storage_temp_C[CURRENT_MARKET_SLOT] == 49.717241379310344
        assert (energy_params.state._min_energy_demand_kWh[CURRENT_MARKET_SLOT] ==
                0.0009956960711739187)
        assert (energy_params.state._max_energy_demand_kWh[CURRENT_MARKET_SLOT] ==
                0.027405927227311375)

    @staticmethod
    def test_event_traded_energy_decrements_posted_energy(energy_params):
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        traded_energy = 0.00001
        original_min_demand = energy_params.state._min_energy_demand_kWh[CURRENT_MARKET_SLOT]
        original_max_demand = energy_params.state._max_energy_demand_kWh[CURRENT_MARKET_SLOT]
        energy_params.event_traded_energy(CURRENT_MARKET_SLOT, traded_energy)
        assert (energy_params.state._min_energy_demand_kWh[CURRENT_MARKET_SLOT] ==
                original_min_demand - traded_energy)
        assert (energy_params.state._max_energy_demand_kWh[CURRENT_MARKET_SLOT] ==
                original_max_demand - traded_energy)

    @staticmethod
    def test_event_traded_energy_updates_temp_increase(energy_params):
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        traded_energy = 0.00001
        energy_params.event_traded_energy(CURRENT_MARKET_SLOT, traded_energy)
        next_time_slot = CURRENT_MARKET_SLOT + GlobalConfig.slot_length
        assert energy_params.state._temp_increase_K[CURRENT_MARKET_SLOT] == 0
        assert energy_params.state._temp_increase_K[next_time_slot] == 0.005679617081471157

    @staticmethod
    def test_get_min_energy_demand_kWh_returns_correct_value(energy_params):
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        energy_params.get_min_energy_demand_kWh(CURRENT_MARKET_SLOT)
        assert (energy_params.get_min_energy_demand_kWh(CURRENT_MARKET_SLOT) ==
                0.0009956960711739187)

    @staticmethod
    def test_get_max_energy_demand_kWh_returns_correct_value(energy_params):
        energy_params.event_market_cycle(CURRENT_MARKET_SLOT)
        energy_params.get_max_energy_demand_kWh(CURRENT_MARKET_SLOT)
        assert (energy_params.get_max_energy_demand_kWh(CURRENT_MARKET_SLOT) ==
                0.027405927227311375)
