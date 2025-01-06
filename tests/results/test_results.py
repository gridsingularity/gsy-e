"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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

from unittest.mock import Mock, patch

from gsy_framework.constants_limits import TIME_ZONE
from pendulum import duration, today

from gsy_e.gsy_e_core.simulation import Simulation
from gsy_e.models.config import SimulationConfig

class TestResults:
    # pylint: disable=protected-access

    @staticmethod
    @patch("gsy_e.gsy_e_core.simulation.external_events.SimulationExternalEvents", Mock())
    def test_results_are_calculated_correctly():
        # Given
        simulation_config = SimulationConfig(
            sim_duration=duration(hours=int(24)),
            slot_length=duration(minutes=int(60)),
            tick_length=duration(seconds=int(60)),
            start_date=today(tz=TIME_ZONE),
            external_connection_enabled=False,
        )
        simulation = Simulation(
            setup_module_name="two_sided_market.default_2a_high_res_graph",
            simulation_config=simulation_config,
            simulation_events=None,
            seed=0,
            paused=False,
            pause_after=duration(),
            repl=False,
            no_export=True,
            export_path=None,
            export_subdir=None,
            redis_job_id="null",
            enable_bc=False,
        )

        # When
        simulation.run()

        # Then
        print("results = ", simulation._results._endpoint_buffer.generate_json_report())
