# pylint: disable=protected-access, attribute-defined-outside-init, too-many-public-methods
import math
from unittest.mock import MagicMock, patch

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.enums import AvailableMarketTypes
from pendulum import UTC, duration, today

from gsy_e.constants import SorTesConfiguration
from gsy_e.models.area import Area
from gsy_e.models.strategy.heat_pump import HeatPumpOrderUpdaterParameters
from gsy_e.models.strategy.heat_pump_soc_management import HeatPumpChargingState
from gsy_e.models.strategy.heatpump_with_sortes_tank import (
    HeatPumpWithSorTesTankStrategy,
    SorTesPerformanceMaps,
    SorTesTankEnergyParameters,
    SorTesTankMinimiseSwitchStrategy,
    SorTesTankState,
)
from gsy_e.models.strategy.strategy_profile import global_objects

START_TIME_SLOT = today(tz=UTC)
SLOT_LENGTH = duration(minutes=15)
NEXT_SLOT = START_TIME_SLOT + SLOT_LENGTH


class TestSorTesPerformanceMaps:

    def test_get_power_charging_at_exact_table_temperatures(self):
        assert math.isclose(SorTesPerformanceMaps.get_power_charging(5), 3.8)
        assert math.isclose(SorTesPerformanceMaps.get_power_charging(20), 3.0)
        assert math.isclose(SorTesPerformanceMaps.get_power_charging(45), 0.5)

    def test_get_power_charging_interpolates_between_table_temperatures(self):
        # Between 10 (3.5 kW) and 15 (3.3 kW), midpoint at 12.5 → 3.4
        power = SorTesPerformanceMaps.get_power_charging(12.5)
        assert math.isclose(power, 3.4, abs_tol=1e-9)

    def test_get_power_charging_extrapolates_below_range(self):
        # Slope from (5, 3.8) to (10, 3.5): -0.06/°C; at 0°C: 3.8 + (-0.06) * (0-5) = 4.1
        power = SorTesPerformanceMaps.get_power_charging(0)
        assert math.isclose(power, 4.1, abs_tol=1e-9)

    def test_get_power_charging_extrapolates_above_range(self):
        # Slope from (40, 1.5) to (45, 0.5): -0.2/°C; at 50°C: 0.5 + (-0.2) * (50-45) = -0.5
        power = SorTesPerformanceMaps.get_power_charging(50)
        assert math.isclose(power, -0.5, abs_tol=1e-9)

    def test_get_power_discharging_at_exact_table_temperatures(self):
        assert math.isclose(SorTesPerformanceMaps.get_power_discharging(5), 3.0)
        assert math.isclose(SorTesPerformanceMaps.get_power_discharging(15), 4.0)
        assert math.isclose(SorTesPerformanceMaps.get_power_discharging(25), 4.8)

    def test_get_power_discharging_interpolates_between_table_temperatures(self):
        # Between 5 (3.0 kW) and 10 (3.5 kW), midpoint at 7.5 → 3.25
        power = SorTesPerformanceMaps.get_power_discharging(7.5)
        assert math.isclose(power, 3.25, abs_tol=1e-9)

    def test_get_power_discharging_extrapolates_below_range(self):
        # Slope from (5, 3.0) to (10, 3.5): 0.1/°C; at 0°C: 3.0 + 0.1 * (0-5) = 2.5
        power = SorTesPerformanceMaps.get_power_discharging(0)
        assert math.isclose(power, 2.5, abs_tol=1e-9)

    def test_get_power_discharging_extrapolates_above_range(self):
        # Slope from (20, 4.3) to (25, 4.8): 0.1/°C; at 30°C: 4.8 + 0.1 * (30-25) = 5.3
        power = SorTesPerformanceMaps.get_power_discharging(30)
        assert math.isclose(power, 5.3, abs_tol=1e-9)

    def test_charging_power_decreases_with_temperature(self):
        powers = [SorTesPerformanceMaps.get_power_charging(t) for t in range(5, 46, 5)]
        assert all(powers[i] > powers[i + 1] for i in range(len(powers) - 1))

    def test_discharging_power_increases_with_temperature(self):
        powers = [SorTesPerformanceMaps.get_power_discharging(t) for t in range(5, 26, 5)]
        assert all(powers[i] < powers[i + 1] for i in range(len(powers) - 1))


class TestSorTesTankMinimiseSwitchStrategy:

    def setup_method(self):
        self._original_market_maker_rate = GlobalConfig.market_maker_rate
        self._original_slot_length = GlobalConfig.slot_length
        self._original_start_date = GlobalConfig.start_date
        GlobalConfig.slot_length = SLOT_LENGTH
        GlobalConfig.market_maker_rate = {
            START_TIME_SLOT: 30,
            NEXT_SLOT: 20,
        }
        GlobalConfig.start_date = START_TIME_SLOT
        self._energy_params_mock = MagicMock()
        self._energy_params_mock.get_soc = MagicMock(return_value=50.0)

    def teardown_method(self):
        GlobalConfig.market_maker_rate = self._original_market_maker_rate
        GlobalConfig.slot_length = self._original_slot_length
        GlobalConfig.start_date = self._original_start_date

    def _create_strategy(self, average_trade_rate=25.0):
        return SorTesTankMinimiseSwitchStrategy(self._energy_params_mock, average_trade_rate)

    def test_initial_state_is_maintain_soc(self):
        strategy = self._create_strategy()
        assert strategy.current_state == HeatPumpChargingState.MAINTAIN_SOC

    def test_current_state_property_returns_current_state(self):
        strategy = self._create_strategy()
        strategy._current_state = HeatPumpChargingState.CHARGE
        assert strategy.current_state == HeatPumpChargingState.CHARGE

    def test_get_tank_soc_delegates_to_energy_params(self):
        strategy = self._create_strategy()
        self._energy_params_mock.get_soc = MagicMock(return_value=42.0)
        soc = strategy._get_tank_soc(START_TIME_SLOT)
        assert math.isclose(soc, 42.0)
        self._energy_params_mock.get_soc.assert_called_once_with(START_TIME_SLOT)

    def test_is_energy_affordable_true_when_avg_rate_below_market_maker_rate(self):
        # average_trade_rate=25, market_maker_rate[START_TIME_SLOT]=30 → 25 < 30 → True
        strategy = self._create_strategy(average_trade_rate=25.0)
        strategy.event_activate()
        assert strategy._is_energy_affordable(START_TIME_SLOT, 0.0) is True

    def test_is_energy_affordable_false_when_avg_rate_above_market_maker_rate(self):
        # average_trade_rate=35, market_maker_rate[START_TIME_SLOT]=30 → 35 < 30 → False
        strategy = self._create_strategy(average_trade_rate=35.0)
        strategy.event_activate()
        assert strategy._is_energy_affordable(START_TIME_SLOT, 0.0) is False

    def test_event_activate_calls_read_or_rotate_profiles(self):
        strategy = self._create_strategy()
        with patch.object(strategy._average_trade_rate, "read_or_rotate_profiles") as mock_rotate:
            strategy.event_activate()
            mock_rotate.assert_called_once()

    def test_event_market_slot_calls_read_or_rotate_profiles(self):
        strategy = self._create_strategy()
        strategy.event_activate()
        with patch.object(strategy._average_trade_rate, "read_or_rotate_profiles") as mock_rotate:
            strategy.event_market_slot()
            mock_rotate.assert_called_once()

    def test_minutes_before_switch_taken_from_sortes_configuration(self):
        assert (
            SorTesTankMinimiseSwitchStrategy.MINUTES_BEFORE_SWITCH_ALLOWED
            == SorTesConfiguration.MINUTES_BEFORE_SWITCH_ALLOWED
        )

    def test_soc_tolerances_taken_from_sortes_configuration(self):
        assert (
            SorTesTankMinimiseSwitchStrategy.MIN_SOC_TOLERANCE
            == SorTesConfiguration.MIN_SOC_TOLERANCE
        )
        assert (
            SorTesTankMinimiseSwitchStrategy.MAX_SOC_TOLERANCE
            == SorTesConfiguration.MAX_SOC_TOLERANCE
        )


class TestSorTesTankState:

    def setup_method(self):
        self._original_start_date = GlobalConfig.start_date
        self._original_slot_length = GlobalConfig.slot_length
        GlobalConfig.slot_length = SLOT_LENGTH
        GlobalConfig.start_date = START_TIME_SLOT
        self._state = SorTesTankState()

    def teardown_method(self):
        GlobalConfig.start_date = self._original_start_date
        GlobalConfig.slot_length = self._original_slot_length

    def test_activate_sets_initial_soc_to_min_soc_tolerance(self):
        self._state.activate()
        assert math.isclose(
            self._state.get_soc(START_TIME_SLOT), SorTesConfiguration.MIN_SOC_TOLERANCE
        )

    def test_get_soc_returns_zero_for_unknown_time_slot(self):
        assert self._state.get_soc(START_TIME_SLOT) == 0.0

    def test_set_and_get_soc_round_trips(self):
        self._state.set_soc(START_TIME_SLOT, 55.0)
        assert math.isclose(self._state.get_soc(START_TIME_SLOT), 55.0)

    def test_set_and_get_min_energy_demand_kWh(self):
        self._state.set_min_energy_demand_kWh(START_TIME_SLOT, 1.5)
        assert math.isclose(self._state.get_min_energy_demand_kWh(START_TIME_SLOT), 1.5)

    def test_get_min_energy_demand_kWh_returns_zero_for_unknown_time_slot(self):
        assert self._state.get_min_energy_demand_kWh(START_TIME_SLOT) == 0.0

    def test_set_and_get_max_energy_demand_kWh(self):
        self._state.set_max_energy_demand_kWh(START_TIME_SLOT, 3.0)
        assert math.isclose(self._state.get_max_energy_demand_kWh(START_TIME_SLOT), 3.0)

    def test_get_max_energy_demand_kWh_returns_zero_for_unknown_time_slot(self):
        assert self._state.get_max_energy_demand_kWh(START_TIME_SLOT) == 0.0

    def test_update_total_charged_energy_kWh_accumulates_over_calls(self):
        self._state.update_total_charged_energy_kWh(2.0)
        self._state.update_total_charged_energy_kWh(3.0)
        assert math.isclose(self._state.get_state()["total_charge_energy_kWh"], 5.0)

    def test_increase_total_traded_energy_kWh_accumulates_over_calls(self):
        self._state.increase_total_traded_energy_kWh(4.0)
        self._state.increase_total_traded_energy_kWh(1.0)
        assert math.isclose(self._state.get_state()["total_traded_energy_kWh"], 5.0)

    def test_delete_past_state_values_removes_slots_older_than_current(self):
        self._state.set_soc(START_TIME_SLOT, 50.0)
        self._state.set_soc(NEXT_SLOT, 60.0)
        # current_time_slot is two slots ahead; START_TIME_SLOT should be removed
        self._state.delete_past_state_values(NEXT_SLOT + SLOT_LENGTH)
        assert self._state.get_soc(START_TIME_SLOT) == 0.0
        assert math.isclose(self._state.get_soc(NEXT_SLOT), 60.0)

    def test_delete_past_state_values_is_noop_when_no_time_slot_given(self):
        self._state.set_soc(START_TIME_SLOT, 50.0)
        self._state.delete_past_state_values(None)
        assert math.isclose(self._state.get_soc(START_TIME_SLOT), 50.0)

    def test_get_state_contains_all_required_keys(self):
        state = self._state.get_state()
        for key in (
            "soc",
            "cop",
            "energy_demand_kWh",
            "min_energy_demand_kWh",
            "max_energy_demand_kWh",
            "total_traded_energy_kWh",
            "total_charge_energy_kWh",
        ):
            assert key in state

    def test_restore_state_round_trips_all_numeric_fields(self):
        self._state.set_soc(START_TIME_SLOT, 70.0)
        self._state.set_cop(START_TIME_SLOT, 4.0)
        self._state.set_energy_demand_kWh(START_TIME_SLOT, 1.5)
        self._state.set_min_energy_demand_kWh(START_TIME_SLOT, 0.5)
        self._state.set_max_energy_demand_kWh(START_TIME_SLOT, 2.0)
        self._state.increase_total_traded_energy_kWh(3.0)
        self._state.update_total_charged_energy_kWh(2.0)

        state_dict = self._state.get_state()
        restored = SorTesTankState()
        restored.restore_state(state_dict)

        assert math.isclose(restored.get_soc(START_TIME_SLOT), 70.0)
        assert math.isclose(restored.get_cop(START_TIME_SLOT), 4.0)
        assert math.isclose(restored.get_energy_demand_kWh(START_TIME_SLOT), 1.5)
        assert math.isclose(restored.get_min_energy_demand_kWh(START_TIME_SLOT), 0.5)
        assert math.isclose(restored.get_max_energy_demand_kWh(START_TIME_SLOT), 2.0)
        restored_dict = restored.get_state()
        assert math.isclose(restored_dict["total_traded_energy_kWh"], 3.0)
        assert math.isclose(restored_dict["total_charge_energy_kWh"], 2.0)

    def test_get_results_dict_returns_correct_values(self):
        self._state.set_cop(START_TIME_SLOT, 3.2)
        self._state.set_soc(START_TIME_SLOT, 55.0)
        self._state.set_heat_demand_kJ(START_TIME_SLOT, 100.0)
        result = self._state.get_results_dict(START_TIME_SLOT)
        assert math.isclose(result["cop"], 3.2)
        assert math.isclose(result["soc"], 55.0)
        assert math.isclose(result["heat_demand_kJ"], 100.0)
        assert "total_traded_energy_kWh" in result
        assert "total_charge_energy_kWh" in result

    def test_delete_past_state_values_clears_all_time_series_attributes(self):
        self._state.set_soc(START_TIME_SLOT, 50.0)
        self._state.set_cop(START_TIME_SLOT, 3.0)
        self._state.set_heat_demand_kJ(START_TIME_SLOT, 100.0)
        self._state.set_energy_demand_kWh(START_TIME_SLOT, 2.0)
        self._state.set_min_energy_demand_kWh(START_TIME_SLOT, 1.0)
        self._state.set_max_energy_demand_kWh(START_TIME_SLOT, 3.0)
        self._state.delete_past_state_values(NEXT_SLOT + SLOT_LENGTH)
        assert self._state.get_soc(START_TIME_SLOT) == 0.0
        assert self._state.get_cop(START_TIME_SLOT) == 0.0
        assert self._state.get_heat_demand_kJ(START_TIME_SLOT) == 0.0
        assert self._state.get_energy_demand_kWh(START_TIME_SLOT) == 0.0
        assert self._state.get_min_energy_demand_kWh(START_TIME_SLOT) == 0.0
        assert self._state.get_max_energy_demand_kWh(START_TIME_SLOT) == 0.0


AMBIENT_TEMP_C = 15.0
TARGET_TEMP_C = 50.0
# delta = 35 → COP = 6.08 - 0.09*35 + 0.0005*35^2 = 6.08 - 3.15 + 0.6125 = 3.5425
EXPECTED_COP = 6.08 - 0.09 * 35 + 0.0005 * 35**2

# SorTesPerformanceMaps.get_power_charging(AMBIENT_TEMP_C + 5) = get_power_charging(20) = 3.0 kW
# With 15-min slot: 3.0 kW * 0.25 h = 0.75 kWh
EXPECTED_CHARGE_ENERGY_KWH = 3.0 * 0.25

# SorTesPerformanceMaps.get_power_discharging(AMBIENT_TEMP_C + 5)
# = get_power_discharging(20) = 4.3 kW
# With 15-min slot: 4.3 kW * 0.25 h = 1.075 kWh
EXPECTED_DISCHARGE_ENERGY_KWH = 4.3 * 0.25


class TestSorTesTankEnergyParameters:

    def setup_method(self):
        self._original_start_date = GlobalConfig.start_date
        self._original_slot_length = GlobalConfig.slot_length
        self._original_market_maker_rate = GlobalConfig.market_maker_rate
        self._original_timestamp = global_objects.profiles_handler.current_timestamp
        GlobalConfig.slot_length = SLOT_LENGTH
        GlobalConfig.start_date = START_TIME_SLOT
        GlobalConfig.market_maker_rate = {
            START_TIME_SLOT: 30,
            NEXT_SLOT: 30,
        }
        global_objects.profiles_handler._update_current_time(timestamp=START_TIME_SLOT)

    def teardown_method(self):
        GlobalConfig.start_date = self._original_start_date
        GlobalConfig.slot_length = self._original_slot_length
        GlobalConfig.market_maker_rate = self._original_market_maker_rate
        global_objects.profiles_handler._update_current_time(timestamp=self._original_timestamp)

    def _create_energy_params(
        self,
        heat_demand_Q_profile=None,
        ambient_temp_C_profile=None,
        target_temp_C_profile=None,
        average_trade_rate=25.0,
    ):
        if heat_demand_Q_profile is None:
            heat_demand_Q_profile = {START_TIME_SLOT: 3600.0, NEXT_SLOT: 3600.0}
        if ambient_temp_C_profile is None:
            ambient_temp_C_profile = {START_TIME_SLOT: AMBIENT_TEMP_C, NEXT_SLOT: AMBIENT_TEMP_C}
        if target_temp_C_profile is None:
            target_temp_C_profile = {START_TIME_SLOT: TARGET_TEMP_C, NEXT_SLOT: TARGET_TEMP_C}
        return SorTesTankEnergyParameters(
            heat_demand_Q_profile=heat_demand_Q_profile,
            ambient_temp_C_profile=ambient_temp_C_profile,
            target_temp_C_profile=target_temp_C_profile,
            average_trade_rate=average_trade_rate,
        )

    def test_state_property_returns_sortes_tank_state_instance(self):
        ep = self._create_energy_params()
        assert isinstance(ep.state, SorTesTankState)

    def test_soc_management_property_returns_switch_strategy_instance(self):
        ep = self._create_energy_params()
        assert isinstance(ep.soc_management, SorTesTankMinimiseSwitchStrategy)

    def test_event_activate_sets_initial_soc_at_start_date(self):
        ep = self._create_energy_params()
        ep.event_activate()
        assert math.isclose(
            ep.state.get_soc(START_TIME_SLOT), SorTesConfiguration.MIN_SOC_TOLERANCE
        )

    def test_get_soc_delegates_to_state(self):
        ep = self._create_energy_params()
        ep.state.set_soc(START_TIME_SLOT, 45.0)
        assert math.isclose(ep.get_soc(START_TIME_SLOT), 45.0)

    def test_get_energy_demand_kWh_delegates_to_state(self):
        ep = self._create_energy_params()
        ep.state.set_energy_demand_kWh(START_TIME_SLOT, 2.0)
        assert math.isclose(ep.get_energy_demand_kWh(START_TIME_SLOT), 2.0)

    def test_get_min_energy_demand_kWh_delegates_to_state(self):
        ep = self._create_energy_params()
        ep.state.set_min_energy_demand_kWh(START_TIME_SLOT, 0.5)
        assert math.isclose(ep.get_min_energy_demand_kWh(START_TIME_SLOT), 0.5)

    def test_get_max_energy_demand_kWh_delegates_to_state(self):
        ep = self._create_energy_params()
        ep.state.set_max_energy_demand_kWh(START_TIME_SLOT, 3.0)
        assert math.isclose(ep.get_max_energy_demand_kWh(START_TIME_SLOT), 3.0)

    def test_last_time_slot_returns_slot_minus_slot_length(self):
        assert SorTesTankEnergyParameters.last_time_slot(NEXT_SLOT) == START_TIME_SLOT

    def test_event_traded_energy_decrements_all_demand_values(self):
        ep = self._create_energy_params()
        ep.state.set_energy_demand_kWh(START_TIME_SLOT, 5.0)
        ep.state.set_min_energy_demand_kWh(START_TIME_SLOT, 2.0)
        ep.state.set_max_energy_demand_kWh(START_TIME_SLOT, 8.0)
        ep.event_traded_energy(START_TIME_SLOT, 3.0)
        assert math.isclose(ep.get_energy_demand_kWh(START_TIME_SLOT), 2.0)
        assert math.isclose(ep.get_min_energy_demand_kWh(START_TIME_SLOT), 0.0)
        assert math.isclose(ep.get_max_energy_demand_kWh(START_TIME_SLOT), 5.0)

    def test_event_traded_energy_clamps_demand_to_zero_when_trade_exceeds_demand(self):
        ep = self._create_energy_params()
        ep.state.set_energy_demand_kWh(START_TIME_SLOT, 1.0)
        ep.state.set_min_energy_demand_kWh(START_TIME_SLOT, 0.5)
        ep.state.set_max_energy_demand_kWh(START_TIME_SLOT, 1.0)
        ep.event_traded_energy(START_TIME_SLOT, 10.0)
        assert ep.get_energy_demand_kWh(START_TIME_SLOT) == 0.0
        assert ep.get_min_energy_demand_kWh(START_TIME_SLOT) == 0.0
        assert ep.get_max_energy_demand_kWh(START_TIME_SLOT) == 0.0

    def test_event_traded_energy_accumulates_total_traded(self):
        ep = self._create_energy_params()
        ep.state.set_energy_demand_kWh(START_TIME_SLOT, 5.0)
        ep.state.set_min_energy_demand_kWh(START_TIME_SLOT, 5.0)
        ep.state.set_max_energy_demand_kWh(START_TIME_SLOT, 5.0)
        ep.event_traded_energy(START_TIME_SLOT, 2.0)
        ep.event_traded_energy(START_TIME_SLOT, 1.5)
        assert math.isclose(ep.state.get_state()["total_traded_energy_kWh"], 3.5)

    def test_event_market_cycle_sets_positive_energy_demand_in_state(self):
        ep = self._create_energy_params()
        ep.event_activate()
        ep.event_market_cycle(START_TIME_SLOT)
        assert ep.get_energy_demand_kWh(START_TIME_SLOT) > 0

    def test_event_market_cycle_sets_cop_for_time_slot(self):
        ep = self._create_energy_params()
        ep.event_activate()
        ep.event_market_cycle(START_TIME_SLOT)
        assert math.isclose(ep.state.get_cop(START_TIME_SLOT), EXPECTED_COP, abs_tol=1e-6)

    def test_event_market_cycle_sets_heat_demand_in_state(self):
        heat_demand_J = 3600.0  # 3.6 kJ = 0.001 kWh
        ep = self._create_energy_params(
            heat_demand_Q_profile={START_TIME_SLOT: heat_demand_J, NEXT_SLOT: heat_demand_J}
        )
        ep.event_activate()
        ep.event_market_cycle(START_TIME_SLOT)
        assert math.isclose(
            ep.state.get_heat_demand_kJ(START_TIME_SLOT), heat_demand_J / 1000.0, abs_tol=1e-9
        )

    def test_event_market_cycle_min_demand_not_greater_than_max_demand(self):
        ep = self._create_energy_params()
        ep.event_activate()
        ep.event_market_cycle(START_TIME_SLOT)
        assert ep.get_min_energy_demand_kWh(NEXT_SLOT) <= ep.get_max_energy_demand_kWh(NEXT_SLOT)

    def test_event_market_cycle_max_demand_exceeds_base_electricity_demand(self):
        # max includes storage charging on top of baseline heat demand
        ep = self._create_energy_params()
        ep.event_activate()
        ep.event_market_cycle(START_TIME_SLOT)
        assert ep.get_max_energy_demand_kWh(NEXT_SLOT) >= ep.get_energy_demand_kWh(NEXT_SLOT)

    def test_no_charge_maintains_soc_from_previous_slot(self):
        ep = self._create_energy_params()
        ep.event_activate()
        # State starts at MIN_SOC_TOLERANCE; soc_management defaults to MAINTAIN_SOC
        ep.event_market_cycle(NEXT_SLOT)
        expected_soc = SorTesConfiguration.MIN_SOC_TOLERANCE
        assert math.isclose(ep.get_soc(NEXT_SLOT), expected_soc)

    def test_charge_increases_soc(self):
        ep = self._create_energy_params()
        ep.event_activate()
        ep.soc_management._current_state = HeatPumpChargingState.CHARGE
        # Simulate that we already bought more than needed for baseline heat
        # charge_energy = 0.75 kWh; condenser = charge * CONVERSION_CHARGE_CONDENSER = 0.625 kWh
        # heat_energy = net_traded * COP_HEAT_SOURCE = (condenser + charge) * 1 = 1.375 kWh
        charge_kWh = EXPECTED_CHARGE_ENERGY_KWH
        condenser_kWh = charge_kWh * SorTesConfiguration.CONVERSION_CHARGE_CONDENSER_POWER
        ep._bought_energy_kWh = charge_kWh + condenser_kWh  # net positive after heat demand
        # Call _update_last_time_slot_data which also resets _bought_energy_kWh
        ep._ambient_temp_C.profile[START_TIME_SLOT] = AMBIENT_TEMP_C
        ep._charge_or_discharge_tank(NEXT_SLOT)
        assert ep.get_soc(NEXT_SLOT) == 13

    def test_discharge_decreases_soc(self):
        ep = self._create_energy_params()
        ep.event_activate()
        # Set SOC high enough to discharge
        high_soc = 50.0
        ep.state.set_soc(START_TIME_SLOT, high_soc)
        ep.soc_management._current_state = HeatPumpChargingState.DISCHARGE
        # Simulate negative net energy (bought less than needed)
        discharge_kWh = EXPECTED_DISCHARGE_ENERGY_KWH
        evaporator_kWh = discharge_kWh * SorTesConfiguration.CONVERSION_DISCHARGE_EVAPORATOR_POWER
        ep._bought_energy_kWh = -evaporator_kWh  # net negative
        ep._ambient_temp_C.profile[START_TIME_SLOT] = AMBIENT_TEMP_C
        ep._charge_or_discharge_tank(NEXT_SLOT)
        assert ep.get_soc(NEXT_SLOT) == 46.5


class TestHeatPumpWithSorTesTankStrategy:

    def setup_method(self):
        self._original_start_date = GlobalConfig.start_date
        self._original_slot_length = GlobalConfig.slot_length
        self._original_market_maker_rate = GlobalConfig.market_maker_rate
        self._original_market_type = ConstSettings.MASettings.MARKET_TYPE
        self._original_timestamp = global_objects.profiles_handler.current_timestamp
        GlobalConfig.slot_length = SLOT_LENGTH
        GlobalConfig.start_date = START_TIME_SLOT
        GlobalConfig.market_maker_rate = {
            START_TIME_SLOT: 30,
            NEXT_SLOT: 30,
        }
        ConstSettings.MASettings.MARKET_TYPE = 2
        global_objects.profiles_handler._update_current_time(timestamp=START_TIME_SLOT)

    def teardown_method(self):
        GlobalConfig.start_date = self._original_start_date
        GlobalConfig.slot_length = self._original_slot_length
        GlobalConfig.market_maker_rate = self._original_market_maker_rate
        ConstSettings.MASettings.MARKET_TYPE = self._original_market_type
        global_objects.profiles_handler._update_current_time(timestamp=self._original_timestamp)

    def _create_strategy(self, **kwargs):
        defaults = {
            "heat_demand_Q_profile": {START_TIME_SLOT: 3600.0, NEXT_SLOT: 3600.0},
            "ambient_temp_C_profile": {START_TIME_SLOT: AMBIENT_TEMP_C, NEXT_SLOT: AMBIENT_TEMP_C},
            "target_temp_C_profile": {START_TIME_SLOT: TARGET_TEMP_C, NEXT_SLOT: TARGET_TEMP_C},
            "average_trade_rate": 25.0,
        }
        defaults.update(kwargs)
        return HeatPumpWithSorTesTankStrategy(**defaults)

    def _create_activated_strategy(self, **kwargs):
        strategy = self._create_strategy(**kwargs)
        strategy_area = Area("sortes_hp", strategy=strategy)
        area = Area("grid", children=[strategy_area])
        area.config.start_date = START_TIME_SLOT
        area.config.end_date = area.config.start_date.add(days=1)
        area.activate()
        return strategy, area

    def test_state_property_returns_sortes_tank_state(self):
        strategy = self._create_strategy()
        assert isinstance(strategy.state, SorTesTankState)

    def test_energy_params_is_sortes_tank_energy_parameters(self):
        strategy = self._create_strategy()
        assert isinstance(strategy._energy_params, SorTesTankEnergyParameters)

    def test_init_with_no_order_updater_params_uses_spot_default(self):
        strategy = self._create_strategy()
        assert AvailableMarketTypes.SPOT in strategy._order_updater_params
        assert isinstance(
            strategy._order_updater_params[AvailableMarketTypes.SPOT],
            HeatPumpOrderUpdaterParameters,
        )

    def test_init_with_custom_order_updater_params_stores_them(self):
        custom_params = {
            AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters(
                initial_rate=5, final_rate=25
            )
        }
        strategy = self._create_strategy(order_updater_parameters=custom_params)
        assert strategy._order_updater_params == custom_params

    def test_event_market_cycle_creates_order_updater_for_spot_market(self):
        strategy, area = self._create_activated_strategy()
        strategy._energy_params.get_max_energy_demand_kWh = MagicMock(return_value=1.0)
        strategy.event_market_cycle()
        market_object = area.spot_market
        assert len(strategy._order_updaters[market_object].keys()) == 1

    def test_event_market_cycle_posts_bid_on_spot_market(self):
        strategy, area = self._create_activated_strategy()
        energy_to_buy = 2.5
        strategy._energy_params.get_max_energy_demand_kWh = MagicMock(return_value=energy_to_buy)
        strategy.event_market_cycle()
        bids = list(area.spot_market.bids.values())
        assert len(bids) == 1
        assert math.isclose(bids[0].energy, energy_to_buy)

    def test_post_order_with_explicit_rate_calls_internal_post_order(self):
        strategy, area = self._create_activated_strategy()
        market = area.spot_market
        market_slot = area.spot_market.time_slot
        strategy._energy_params.soc_management.calculate = MagicMock(return_value=1.5)
        strategy._post_order = MagicMock()
        strategy.post_order(market, market_slot, order_rate=15.0)
        strategy._post_order.assert_called_once()

    def test_post_order_uses_soc_management_calculate_for_energy(self):
        strategy, area = self._create_activated_strategy()
        market = area.spot_market
        market_slot = area.spot_market.time_slot
        expected_energy = 2.0
        strategy._energy_params.soc_management.calculate = MagicMock(return_value=expected_energy)
        captured_args = {}

        def capture_post_order(_mkt, _slot, energy, _rate):
            captured_args["energy"] = float(energy)

        strategy._post_order = capture_post_order
        strategy.post_order(market, market_slot, order_rate=15.0)
        assert math.isclose(captured_args["energy"], expected_energy)

    def test_state_is_same_object_as_energy_params_state(self):
        strategy = self._create_strategy()
        assert strategy.state is strategy._energy_params.state
