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
import unittest
from unittest.mock import MagicMock

from gsy_framework.constants_limits import TIME_ZONE, GlobalConfig
from gsy_framework.kafka_communication.kafka_producer import (DisabledKafkaConnection,
                                                              KafkaConnection)
from gsy_framework.sim_results.all_results import ResultsHandler
from pendulum import duration, today

from gsy_e.gsy_e_core.sim_results.endpoint_buffer import SimulationEndpointBuffer
from gsy_e.gsy_e_core.simulation import Simulation
from gsy_e.models.config import SimulationConfig


class SimulationTest(unittest.TestCase):

    def tearDown(self) -> None:
        GlobalConfig.sim_duration = duration(days=GlobalConfig.DURATION_D)
        GlobalConfig.slot_length = duration(minutes=GlobalConfig.SLOT_LENGTH_M)
        GlobalConfig.tick_length = duration(seconds=GlobalConfig.TICK_LENGTH_S)

    @staticmethod
    def test_results_are_sent_via_kafka_if_not_started_from_cli():
        redis_job_id = None
        simulation_config = SimulationConfig(duration(hours=int(12)),
                                             duration(minutes=int(60)),
                                             duration(seconds=int(60)),
                                             cloud_coverage=0,
                                             market_maker_rate=30,
                                             start_date=today(tz=TIME_ZONE),
                                             external_connection_enabled=False)
        simulation = Simulation(
            "default_2a", simulation_config, None, 0, False, duration(), False, False, None, None,
            redis_job_id, False
        )
        simulation.endpoint_buffer = MagicMock(spec=SimulationEndpointBuffer)
        results_mapping = ResultsHandler().results_mapping
        simulation.endpoint_buffer.results_handler = MagicMock(spec=ResultsHandler)
        simulation.kafka_connection = MagicMock(spec=DisabledKafkaConnection)
        simulation.endpoint_buffer.results_handler.all_ui_results = {
            k: {} for k in results_mapping}

        simulation._update_and_send_results()

        assert not simulation.endpoint_buffer.prepare_results_for_publish.called
        assert not simulation.kafka_connection.publish.called

    @staticmethod
    def test_results_not_send_via_kafka_if_started_from_cli():
        redis_job_id = "1234"
        simulation_config = SimulationConfig(duration(hours=int(12)),
                                             duration(minutes=int(60)),
                                             duration(seconds=int(60)),
                                             cloud_coverage=0,
                                             market_maker_rate=30,
                                             start_date=today(tz=TIME_ZONE),
                                             external_connection_enabled=False)
        simulation = Simulation(
            "default_2a", simulation_config, None, 0, False, duration(), False, True, None, None,
            redis_job_id, False
        )
        simulation.endpoint_buffer = MagicMock(spec=SimulationEndpointBuffer)
        results_mapping = ResultsHandler().results_mapping
        simulation.endpoint_buffer.results_handler = MagicMock(spec=ResultsHandler)
        simulation.kafka_connection = MagicMock(spec=KafkaConnection)
        simulation.endpoint_buffer.results_handler.all_ui_results = {
            k: {} for k in results_mapping}

        simulation._update_and_send_results()

        simulation.endpoint_buffer.prepare_results_for_publish.assert_called_once()
        simulation.kafka_connection.publish.assert_called_once()
