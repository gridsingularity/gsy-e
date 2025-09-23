import math
from unittest.mock import MagicMock
import pytest

from pendulum import datetime, duration

from gsy_framework.constants_limits import GlobalConfig

from gsy_e.models.strategy.energy_parameters.heatpump.heat_pump import (
    HeatPumpEnergyParameters,
    HeatChargerDischarger,
    CombinedHeatpumpTanksState,
)
from gsy_e.models.strategy.heat_pump_soc_management import MinimiseHeatpumpSwitchStrategy


@pytest.fixture(name="minimize_heatpump_switch_strategy")
def fixture_minimize_heatpump_switch_strategy():
    return


class TestMinimiseHeatpumpSwitchStrategy:
    # pylint: disable=protected-access,attribute-defined-outside-init
    # pylint: disable=unsupported-assignment-operation
    def setup_method(self):
        self._market_maker_rate = GlobalConfig.MARKET_MAKER_RATE
        self._start_time_slot = datetime(2025, 2, 2, 0, 0, 0)
        GlobalConfig.market_maker_rate = {
            self._start_time_slot: 30,
            self._start_time_slot + duration(minutes=15): 40,
            self._start_time_slot + duration(minutes=30): 50,
        }

    def teardown_method(self):
        GlobalConfig.MARKET_MAKER_RATE = self._market_maker_rate

    def _create_minimize_heatpump_switch_strategy(self, energy_params):
        strategy = MinimiseHeatpumpSwitchStrategy(energy_params)
        strategy.event_activate()
        return strategy

    def _energy_params_mock(self, max_energy=10, min_energy=1, soc=50):
        energy_params = MagicMock(spec=HeatPumpEnergyParameters)
        energy_params.get_min_energy_demand_kWh = MagicMock(return_value=min_energy)
        energy_params.get_max_energy_demand_kWh = MagicMock(return_value=max_energy)
        energy_params.combined_state = MagicMock(spec=CombinedHeatpumpTanksState)
        energy_params.combined_state._charger = MagicMock(spec=HeatChargerDischarger)
        energy_params.combined_state._charger.get_average_soc = MagicMock(return_value=soc)
        return energy_params

    def test_charge_when_rate_is_cheap_and_soc_below_max(self):
        energy_params = self._energy_params_mock()
        strategy = self._create_minimize_heatpump_switch_strategy(energy_params)

        energy = strategy.calculate(time_slot=self._start_time_slot)
        assert math.isclose(energy, 10.0)

    def test_discharge_when_rate_is_expensive_and_soc_above_min(self):
        energy_params = self._energy_params_mock(soc=50)
        strategy = self._create_minimize_heatpump_switch_strategy(energy_params)

        energy = strategy.calculate(time_slot=self._start_time_slot + duration(minutes=30))

        assert math.isclose(energy, 1.0)

    def test_maintain_soc_when_rate_is_expensive_and_soc_min(self):
        energy_params = self._energy_params_mock(
            soc=MinimiseHeatpumpSwitchStrategy.MIN_SOC_TOLERANCE
        )
        strategy = self._create_minimize_heatpump_switch_strategy(energy_params)

        energy = strategy.calculate(time_slot=self._start_time_slot + duration(minutes=30))

        assert math.isclose(energy, 1.0)

    def test_maintain_when_rate_is_cheap_but_soc_at_or_above_max(self):
        energy_params = self._energy_params_mock(
            soc=MinimiseHeatpumpSwitchStrategy.MAX_SOC_TOLERANCE
        )
        strategy = self._create_minimize_heatpump_switch_strategy(energy_params)

        energy = strategy.calculate(time_slot=self._start_time_slot)

        assert math.isclose(energy, 1.0)

    def test_do_not_switch_from_charge_to_discharge_before_time_limit(self):
        GlobalConfig.market_maker_rate[self._start_time_slot + duration(minutes=120)] = 50
        energy_params = self._energy_params_mock(soc=50)
        strategy = self._create_minimize_heatpump_switch_strategy(energy_params)

        energy = strategy.calculate(time_slot=self._start_time_slot)
        # Now charging
        assert math.isclose(energy, 10.0)

        energy = strategy.calculate(time_slot=self._start_time_slot + duration(minutes=15))
        # Energy below average, still fully charging
        assert math.isclose(energy, 10.0)

        energy = strategy.calculate(time_slot=self._start_time_slot + duration(minutes=30))
        # Should still not discharge despite the rate being expensive, still fully charging
        assert math.isclose(energy, 10.0)

        energy = strategy.calculate(time_slot=self._start_time_slot + duration(minutes=120))
        # After 2 hours charge allowed, start discharging
        assert math.isclose(energy, 1.0)

    def test_do_not_switch_from_discharge_to_charge_before_time_limit(self):
        GlobalConfig.market_maker_rate[self._start_time_slot] = 50
        GlobalConfig.market_maker_rate[self._start_time_slot + duration(minutes=120)] = 30
        energy_params = self._energy_params_mock(soc=50)
        strategy = self._create_minimize_heatpump_switch_strategy(energy_params)

        energy = strategy.calculate(time_slot=self._start_time_slot)
        # Now discharging
        assert math.isclose(energy, 1.0)

        energy = strategy.calculate(time_slot=self._start_time_slot + duration(minutes=15))
        # Energy above average, still fully discharging
        assert math.isclose(energy, 1.0)

        energy = strategy.calculate(time_slot=self._start_time_slot + duration(minutes=30))
        # Should still not charge despite the rate being cheap, still fully charging
        assert math.isclose(energy, 1.0)

        energy = strategy.calculate(time_slot=self._start_time_slot + duration(minutes=120))
        # After 2 hours discharge allowed, start charging
        assert math.isclose(energy, 10.0)

    def test_maintain_soc_during_time_limit_if_soc_reaches_min(self):
        GlobalConfig.market_maker_rate[self._start_time_slot] = 50
        GlobalConfig.market_maker_rate[self._start_time_slot + duration(minutes=120)] = 30
        energy_params = self._energy_params_mock(soc=50)
        strategy = self._create_minimize_heatpump_switch_strategy(energy_params)

        energy = strategy.calculate(time_slot=self._start_time_slot)
        # Now discharging
        assert math.isclose(energy, 1.0)

        # Set the SOC to min
        energy_params.combined_state._charger.get_average_soc = MagicMock(
            return_value=MinimiseHeatpumpSwitchStrategy.MIN_SOC_TOLERANCE
        )
        # Maintain SOC despite in discharging state
        energy = strategy.calculate(time_slot=self._start_time_slot + duration(minutes=15))
        assert math.isclose(energy, 1.0)

        energy = strategy.calculate(time_slot=self._start_time_slot + duration(minutes=30))
        assert math.isclose(energy, 1.0)
