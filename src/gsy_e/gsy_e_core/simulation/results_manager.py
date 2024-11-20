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

from logging import getLogger
from typing import TYPE_CHECKING, Optional

from gsy_framework.kafka_communication.kafka_producer import kafka_connection_factory
from pendulum import now

import gsy_e.constants
from gsy_e.constants import DATE_TIME_FORMAT, TIME_ZONE
from gsy_e.gsy_e_core.export import ExportAndPlot
from gsy_e.gsy_e_core.sim_results.endpoint_buffer import (
    SimulationEndpointBuffer,
)

if TYPE_CHECKING:
    from gsy_e.models.area import Area, AreaBase
    from gsy_e.gsy_e_core.simulation.setup import SimulationSetup
    from gsy_e.gsy_e_core.simulation.simulation import Simulation

log = getLogger(__name__)


class SimulationResultsManager:
    # pylint: disable=too-many-instance-attributes
    """Maintain and populate the simulation results and the publishing to the message broker."""

    def __init__(
        self,
        export_results_on_finish: bool,
        export_path: str,
        export_subdir: Optional[str],
        started_from_cli: bool,
    ) -> None:
        self.export_results_on_finish = export_results_on_finish
        self.export_path = export_path
        self.started_from_cli = started_from_cli
        self.kafka_connection = kafka_connection_factory()

        if export_subdir is None:
            self.export_subdir = now(tz=TIME_ZONE).format(f"{DATE_TIME_FORMAT}:ss")
        else:
            self.export_subdir = export_subdir
        self._endpoint_buffer = None
        self._export = None

    def init_results(
        self, redis_job_id: str, area: "AreaBase", config_params: "SimulationSetup"
    ) -> None:
        """Construct objects that contain the simulation results for the broker and CSV output."""
        self._endpoint_buffer = SimulationEndpointBuffer(
            redis_job_id, config_params.seed, area, self.export_results_on_finish
        )

        if self.export_results_on_finish:
            self._export = ExportAndPlot(
                area, self.export_path, self.export_subdir, self._endpoint_buffer
            )

    @property
    def _should_send_results_to_broker(self) -> None:
        """Flag that decides whether to send results to the gsy-web"""
        return not self.started_from_cli and self.kafka_connection.is_enabled()

    def create_hierarchy_stats(self, area: "AreaBase"):
        """Trigger calculation of hierarchy related statistics."""
        self._endpoint_buffer.create_hierarchy_stats(area)

    def update_and_send_results(self, simulation: "Simulation"):
        """Update the simulation results.

        This method should be called on init, finish and every market cycle.
        """
        current_state = simulation.current_state
        progress_info = simulation.progress_info
        area = simulation.area

        if self._should_send_results_to_broker:
            self._endpoint_buffer.update_stats(
                area,
                simulation.status.status,
                progress_info,
                current_state,
                calculate_results=False,
            )
            results = self._endpoint_buffer.prepare_results_for_publish()
            if results is None:
                return
            self.kafka_connection.publish(results, current_state["simulation_id"])

        elif gsy_e.constants.RETAIN_PAST_MARKET_STRATEGIES_STATE or self.export_results_on_finish:

            self._endpoint_buffer.update_stats(
                area,
                current_state["sim_status"],
                progress_info,
                current_state,
                calculate_results=True,
            )
            self._update_area_stats(area, self._endpoint_buffer)

            if self.export_results_on_finish:
                assert self._export is not None
                if (
                    area.spot_market is not None
                    and gsy_e.constants.RETAIN_PAST_MARKET_STRATEGIES_STATE
                ):
                    # for integration tests:
                    self._export.raw_data_to_json(
                        area.spot_market.time_slot_str,
                        self._endpoint_buffer.flattened_area_core_stats_dict,
                    )

                self._export.file_stats_endpoint(area)

    @classmethod
    def _update_area_stats(cls, area: "Area", endpoint_buffer: "SimulationEndpointBuffer") -> None:
        for child in area.children:
            cls._update_area_stats(child, endpoint_buffer)
        bills = endpoint_buffer.results_handler.all_ui_results["bills"].get(area.uuid, {})
        area.stats.update_aggregated_stats({"bills": bills})
        area.stats.kpi.update(
            endpoint_buffer.results_handler.all_ui_results["kpi"].get(area.uuid, {})
        )

    def update_csv_on_market_cycle(self, slot_no: int, area: "Area") -> None:
        """Update the csv results on market cycle."""
        if self.export_results_on_finish:
            self._export.data_to_csv(area, slot_no == 0)

    def save_csv_results(self, area: "Area") -> None:
        """Update the CSV results on finish, and write the CSV files."""
        if self.export_results_on_finish:
            log.info("Exporting simulation data.")
            self._export.data_to_csv(area, False)
            self._export.area_tree_summary_to_json(self._endpoint_buffer.area_result_dict)
            self._export.export(power_flow=None)
