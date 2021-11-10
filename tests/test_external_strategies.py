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
import uuid
import json
import pytest
from gsy_e.models.area import Area
from gsy_e.models.strategy.external_strategies.load import (LoadForecastExternalStrategy,
                                                            LoadHoursExternalStrategy)
from gsy_e.models.strategy.external_strategies.pv import (PVForecastExternalStrategy,
                                                          PVExternalStrategy)
from gsy_e.models.strategy.external_strategies.storage import StorageExternalStrategy
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from pendulum import now, duration
from collections import deque
from gsy_e.models.strategy.external_strategies import IncomingRequest


@pytest.fixture
def ext_strategy_fixture(request):
    strategy = request.param
    config = Mock()
    config.slot_length = duration(minutes=15)
    config.tick_length = duration(seconds=15)
    config.ticks_per_slot = 60
    config.start_date = GlobalConfig.start_date
    config.grid_fee_type = ConstSettings.IAASettings.GRID_FEE_TYPE
    config.end_date = GlobalConfig.start_date + duration(days=1)
    area = Area(name="forecast_pv", config=config, strategy=strategy,
                external_connection_available=True)
    parent = Area(name="parent_area", children=[area], config=config)
    parent.activate()
    strategy.connected = True
    market = MagicMock()
    market.time_slot = GlobalConfig.start_date
    return strategy


class TestPVForecastExternalStrategy:

    @pytest.mark.parametrize("ext_strategy_fixture", [LoadForecastExternalStrategy(),
                                                      PVForecastExternalStrategy()], indirect=True)
    def test_event_market_cycle_calls_energy_update_methods(self, ext_strategy_fixture):
        ext_strategy_fixture.energy_forecast_buffer = {now(): 1}
        ext_strategy_fixture.energy_measurement_buffer = {now(): 1}
        ext_strategy_fixture.update_energy_forecast = Mock()
        ext_strategy_fixture.update_energy_measurement = Mock()
        ext_strategy_fixture.event_market_cycle()
        ext_strategy_fixture.update_energy_forecast.assert_called_once()
        ext_strategy_fixture.update_energy_measurement.assert_called_once()
        assert ext_strategy_fixture.energy_forecast_buffer == {}
        assert ext_strategy_fixture.energy_measurement_buffer == {}

    @pytest.mark.parametrize("ext_strategy_fixture", [PVForecastExternalStrategy()],
                             indirect=True)
    def test_update_energy_forecast_calls_set_available_energy(self, ext_strategy_fixture):
        time = ext_strategy_fixture.area.spot_market.time_slot
        energy = 1
        ext_strategy_fixture.energy_forecast_buffer = {time: energy}
        ext_strategy_fixture.state.set_available_energy = Mock()
        ext_strategy_fixture.update_energy_forecast()
        ext_strategy_fixture.state.set_available_energy.assert_called_once_with(
            energy, time, overwrite=True)

    @pytest.mark.parametrize("ext_strategy_fixture", [PVForecastExternalStrategy()],
                             indirect=True)
    def test_update_energy_forecast_doesnt_call_set_available_energy_for_past_markets(
            self, ext_strategy_fixture):
        # do not call set_available_energy for time_slots in the past
        ext_strategy_fixture.state.set_available_energy = Mock()
        time = ext_strategy_fixture.area.spot_market.time_slot.subtract(minutes=15)
        ext_strategy_fixture.energy_forecast_buffer = {time: 1}
        ext_strategy_fixture.update_energy_forecast()
        ext_strategy_fixture.state.set_available_energy.assert_not_called()

    @pytest.mark.parametrize("ext_strategy_fixture", [LoadForecastExternalStrategy()],
                             indirect=True)
    def test_update_energy_forecast_calls_set_desired_energy(self, ext_strategy_fixture):
        time = ext_strategy_fixture.area.spot_market.time_slot
        energy = 1
        ext_strategy_fixture.energy_forecast_buffer = {time: energy}
        ext_strategy_fixture.state.set_desired_energy = Mock()
        ext_strategy_fixture.state.update_total_demanded_energy = Mock()
        ext_strategy_fixture.update_energy_forecast()
        ext_strategy_fixture.state.set_desired_energy.assert_called_once_with(
            energy * 1000, time, overwrite=True)
        ext_strategy_fixture.state.update_total_demanded_energy.assert_called_once_with(time)

    @pytest.mark.parametrize("ext_strategy_fixture", [LoadForecastExternalStrategy()],
                             indirect=True)
    def test_update_energy_forecast_doesnt_call_set_desired_energy_for_past_markets(
            self, ext_strategy_fixture):
        time = ext_strategy_fixture.area.spot_market.time_slot.subtract(minutes=15)
        ext_strategy_fixture.energy_forecast_buffer = {time: 1}
        ext_strategy_fixture.state.set_desired_energy = Mock()
        ext_strategy_fixture.state.update_total_demanded_energy = Mock()
        ext_strategy_fixture.update_energy_forecast()
        ext_strategy_fixture.state.set_desired_energy.assert_not_called()
        ext_strategy_fixture.state.update_total_demanded_energy.assert_not_called()

    @pytest.mark.parametrize("ext_strategy_fixture", [LoadForecastExternalStrategy(),
                                                      PVForecastExternalStrategy()], indirect=True)
    def test_update_energy_measurement_calls_set_energy_measurement_kWh(
            self, ext_strategy_fixture):
        time = ext_strategy_fixture.area.spot_market.time_slot.subtract(minutes=15)
        energy = 1
        ext_strategy_fixture.energy_measurement_buffer = {time: energy}
        ext_strategy_fixture.state.set_energy_measurement_kWh = Mock()
        ext_strategy_fixture.update_energy_measurement()
        ext_strategy_fixture.state.set_energy_measurement_kWh.assert_called_once_with(energy, time)

    @pytest.mark.parametrize("ext_strategy_fixture", [LoadForecastExternalStrategy(),
                                                      PVForecastExternalStrategy()], indirect=True)
    def test_update_energy_measurement_doesnt_call_set_energy_measurement_kWh_for_future_markets(
            self, ext_strategy_fixture):
        time = ext_strategy_fixture.area.spot_market.time_slot.add(minutes=15)
        ext_strategy_fixture.energy_measurement_buffer = {time: 1}
        ext_strategy_fixture.state.set_energy_measurement_kWh = Mock()
        ext_strategy_fixture.update_energy_measurement()
        ext_strategy_fixture.state.set_energy_measurement_kWh.assert_not_called()

    @pytest.mark.parametrize("ext_strategy_fixture", [LoadHoursExternalStrategy(100),
                                                      StorageExternalStrategy()],
                             indirect=True)
    def test_receive_bid_successful(self, ext_strategy_fixture):
        transaction_id = str(uuid.uuid4())
        arguments = {"transaction_id": transaction_id,
                     "price": 1,
                     "energy": 2}
        payload = {"data": json.dumps(arguments)}
        assert ext_strategy_fixture.pending_requests == deque([])
        ext_strategy_fixture.bid(payload)
        assert len(ext_strategy_fixture.pending_requests) > 0
        response_channel = f"{ext_strategy_fixture.channel_prefix}/response/bid"
        assert (ext_strategy_fixture.pending_requests ==
                deque([IncomingRequest("bid", arguments,
                                       response_channel)]))

    @pytest.mark.parametrize("ext_strategy_fixture", [PVExternalStrategy(),
                                                      StorageExternalStrategy()],
                             indirect=True)
    def test_receive_offer_successful(self, ext_strategy_fixture):
        transaction_id = str(uuid.uuid4())
        arguments = {"transaction_id": transaction_id,
                     "price": 1,
                     "energy": 2}
        payload = {"data": json.dumps(arguments)}
        assert ext_strategy_fixture.pending_requests == deque([])
        ext_strategy_fixture.offer(payload)
        assert len(ext_strategy_fixture.pending_requests) > 0
        response_channel = f"{ext_strategy_fixture.channel_prefix}/response/offer"
        assert (ext_strategy_fixture.pending_requests ==
                deque([IncomingRequest("offer", arguments,
                                       response_channel)]))

    @pytest.mark.parametrize("ext_strategy_fixture", [PVExternalStrategy(),
                                                      StorageExternalStrategy()],
                             indirect=True)
    def test_list_offers_successful(self, ext_strategy_fixture):
        transaction_id = str(uuid.uuid4())
        arguments = {"transaction_id": transaction_id}
        payload = {"data": json.dumps(arguments)}
        assert ext_strategy_fixture.pending_requests == deque([])
        ext_strategy_fixture.list_offers(payload)
        assert len(ext_strategy_fixture.pending_requests) > 0
        response_channel = f"{ext_strategy_fixture.channel_prefix}/response/list_offers"
        assert (ext_strategy_fixture.pending_requests ==
                deque([IncomingRequest("list_offers", arguments,
                                       response_channel)]))

    @pytest.mark.parametrize("ext_strategy_fixture", [LoadHoursExternalStrategy(100),
                                                      StorageExternalStrategy()],
                             indirect=True)
    def test_list_bids_successful(self, ext_strategy_fixture):
        transaction_id = str(uuid.uuid4())
        arguments = {"transaction_id": transaction_id}
        payload = {"data": json.dumps(arguments)}
        assert ext_strategy_fixture.pending_requests == deque([])
        ext_strategy_fixture.list_bids(payload)
        assert len(ext_strategy_fixture.pending_requests) > 0
        response_channel = f"{ext_strategy_fixture.channel_prefix}/response/list_bids"
        assert (ext_strategy_fixture.pending_requests ==
                deque([IncomingRequest("list_bids", arguments,
                                       response_channel)]))

    @pytest.mark.parametrize("ext_strategy_fixture", [LoadHoursExternalStrategy(100),
                                                      StorageExternalStrategy()],
                             indirect=True)
    def test_delete_bid_successful(self, ext_strategy_fixture):
        transaction_id = str(uuid.uuid4())
        arguments = {"transaction_id": transaction_id}
        payload = {"data": json.dumps(arguments)}
        assert ext_strategy_fixture.pending_requests == deque([])
        ext_strategy_fixture.delete_bid(payload)
        assert len(ext_strategy_fixture.pending_requests) > 0
        response_channel = f"{ext_strategy_fixture.channel_prefix}/response/delete_bid"
        assert (ext_strategy_fixture.pending_requests ==
                deque([IncomingRequest("delete_bid", arguments,
                                       response_channel)]))

    @pytest.mark.parametrize("ext_strategy_fixture", [PVExternalStrategy(),
                                                      StorageExternalStrategy()],
                             indirect=True)
    def test_delete_offer_successful(self, ext_strategy_fixture):
        transaction_id = str(uuid.uuid4())
        arguments = {"transaction_id": transaction_id}
        payload = {"data": json.dumps(arguments)}
        assert ext_strategy_fixture.pending_requests == deque([])
        ext_strategy_fixture.delete_offer(payload)
        assert len(ext_strategy_fixture.pending_requests) > 0
        response_channel = f"{ext_strategy_fixture.channel_prefix}/response/delete_offer"
        assert (ext_strategy_fixture.pending_requests ==
                deque([IncomingRequest("delete_offer", arguments,
                                       response_channel)]))
