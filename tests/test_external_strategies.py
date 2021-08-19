"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from unittest.mock import MagicMock, Mock

from d3a.models.area import Area
from d3a.models.strategy.external_strategies.load import LoadForecastExternalStrategy
from d3a.models.strategy.external_strategies.pv import PVForecastExternalStrategy
from d3a_interface.constants_limits import GlobalConfig
from pendulum import now, Duration
from pytest import mark


def ext_strategy_fixture(strategy):
    config = MagicMock()
    config.ticks_per_slot = 90
    GlobalConfig.end_date = GlobalConfig.start_date + Duration(days=1)
    area = Area(name="forecast_pv", config=config, strategy=strategy,
                external_connection_available=True)
    parent = Area(name="parent_area", children=[area])
    parent.activate()
    area.activate()
    strategy.connected = True
    market = MagicMock()
    market.time_slot = GlobalConfig.start_date
    parent.get_future_market_from_id = lambda _: market
    area.get_future_market_from_id = lambda _: market
    return strategy


class TestPVForecastExternalStrategy:

    @mark.parametrize("strategy", [ext_strategy_fixture(LoadForecastExternalStrategy()),
                                   ext_strategy_fixture(PVForecastExternalStrategy())])
    def test_clear_energy_buffers(self, strategy):
        strategy.energy_forecast_buffer = {now(): 1}
        strategy.energy_measurement_buffer = {now(): 1}
        strategy._clear_energy_buffers()
        assert strategy.energy_forecast_buffer == {}
        assert strategy.energy_measurement_buffer == {}

    @mark.parametrize("strategy", [ext_strategy_fixture(LoadForecastExternalStrategy()),
                                   ext_strategy_fixture(PVForecastExternalStrategy())])
    def test_event_market_cycle_calls_energy_update_methods(self, strategy):
        strategy.event_market_cycle()
        strategy.update_energy_forecast.assert_called_once()
        strategy.update_energy_measurement.assert_called_once()
        strategy._clear_energy_buffers.assert_called_once()

    def test_update_forecast_calls_set_available_energy(self, strategy=ext_strategy_fixture(
            PVForecastExternalStrategy())):
        time = strategy.area.next_market.time_slot
        energy = 1
        strategy.energy_forecast_buffer = {time: energy}
        strategy.state.set_available_energy = Mock()
        strategy.update_energy_forecast()
        strategy.state.set_available_energy.assert_called_once_with(energy,
                                                                    time, overwrite=True)
        # do not call set_available_energy for time_slots in the past
        time = strategy.area.next_market.time_slot.subtract(minutes=15)
        strategy.energy_forecast_buffer = {time: energy}
        strategy.state.set_available_energy.reset_mock()
        strategy.update_energy_forecast()
        strategy.state.set_available_energy.assert_not_called()

    def test_update_forecast_calls_set_desired_energy_for(self, strategy=ext_strategy_fixture(
            LoadForecastExternalStrategy())):
        time = strategy.area.next_market.time_slot
        energy = 1
        strategy.energy_forecast_buffer = {time: energy}
        strategy.state.set_desired_energy = Mock()
        strategy.state.update_total_demanded_energy = Mock()
        strategy.update_energy_forecast()
        strategy.state.set_desired_energy.assert_called_once_with(energy * 1000,
                                                                  time, overwrite=True)
        strategy.state.update_total_demanded_energy.assert_called_once_with(time)

        # do not call set_available_energy for time_slots in the past
        time = strategy.area.next_market.time_slot.subtract(minutes=15)
        strategy.energy_forecast_buffer = {time: energy}
        strategy.state.set_desired_energy.reset_mock()
        strategy.state.update_total_demanded_energy.reset_mock()
        strategy.update_energy_forecast()
        strategy.state.set_desired_energy.assert_not_called()
        strategy.state.update_total_demanded_energy.assert_not_called()

    @mark.parametrize("strategy", [ext_strategy_fixture(LoadForecastExternalStrategy()),
                                   ext_strategy_fixture(PVForecastExternalStrategy())])
    def test_update_energy_measurement_calls_set_energy_measurement_kWh(self, strategy):
        time = strategy.area.next_market.time_slot.subtract(minutes=15)
        energy = 1
        strategy.energy_measurement_buffer = {time: energy}
        strategy.state.set_energy_measurement_kWh = Mock()
        strategy.update_energy_measurement()
        strategy.state.set_energy_measurement_kWh.assert_called_once_with(energy, time)

        # do not call set_energy_measurement_kWh for time_slots in the future
        time = strategy.area.next_market.time_slot.add(minutes=15)
        strategy.energy_measurement_buffer = {time: energy}
        strategy.state.set_energy_measurement_kWh.reset_mock()
        strategy.update_energy_measurement()
        strategy.state.set_energy_measurement_kWh.assert_not_called()
