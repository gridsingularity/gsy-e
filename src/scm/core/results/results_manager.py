from logging import getLogger
from typing import TYPE_CHECKING

from pendulum import DateTime

import gsy_e.constants
from gsy_e.gsy_e_core.simulation.results_manager import SimulationResultsManager
from scm.core.results.endpoint_buffer import CoefficientEndpointBuffer
from scm.core.results.export import CoefficientExportAndPlot
from scm.scm_manager import SCMManager

if TYPE_CHECKING:
    from scm.coefficient_area import CoefficientArea
    from gsy_e.gsy_e_core.sim_results.endpoint_buffer import SimulationEndpointBuffer
    from gsy_e.gsy_e_core.simulation.setup import SimulationSetup
    from gsy_e.gsy_e_core.simulation.simulation import Simulation

log = getLogger(__name__)


class CoefficientSimulationResultsManager(SimulationResultsManager):
    """Maintain and populate the SCM simulation results and publishing to the message broker."""

    def init_results(
        self, redis_job_id: str, area: "CoefficientArea", config_params: "SimulationSetup"
    ) -> None:
        """Construct objects that contain the simulation results for the broker and CSV output."""
        self._endpoint_buffer = CoefficientEndpointBuffer(
            redis_job_id,
            config_params.seed,
            area,
            self.export_results_on_finish,
            scm_past_slots=config_params.config.scm_past_slots,
        )

        if self.export_results_on_finish:
            self._export = CoefficientExportAndPlot(
                area, self.export_path, self.export_subdir, self._endpoint_buffer
            )

    def update_scm_manager(self, scm_manager: SCMManager) -> None:
        """Update the scm_manager with the latest instance."""
        self._scm_manager = scm_manager

    @classmethod
    def _update_area_stats(
        cls, area: "CoefficientArea", endpoint_buffer: "SimulationEndpointBuffer"
    ) -> None:
        return

    def update_csv_files(
        self,
        slot_no: int,
        current_time_slot: DateTime,
        area: "CoefficientArea",
        scm_manager: SCMManager,
    ) -> None:
        """Update the csv results on market cycle."""
        if self.export_results_on_finish:
            self._export.data_to_csv(area, current_time_slot, slot_no == 0, scm_manager)

    def save_csv_results(self, area: "CoefficientArea") -> None:
        """Update the CSV results on finish, and write the CSV files."""
        if self.export_results_on_finish:
            log.info("Exporting simulation data.")
            self._export.area_tree_summary_to_json(self._endpoint_buffer.area_result_dict)
            self._export.export(power_flow=None)

    def update_and_send_results(self, simulation: "Simulation") -> None:
        """
        Update the coefficient simulation results.
        """
        assert self._endpoint_buffer is not None

        current_state = simulation.current_state
        progress_info = simulation.progress_info
        area = simulation.area
        simulation_status = simulation.status.status
        scm_past_slots = simulation.config.scm_past_slots

        if self._should_send_results_to_broker:
            self._endpoint_buffer.update_coefficient_stats(
                area, simulation_status, progress_info, current_state, False, self._scm_manager
            )
            self._endpoint_buffer.simulation_progress["scm_past_slots"] = scm_past_slots
            results = self._endpoint_buffer.prepare_results_for_publish()
            if results is None:
                return
            self.kafka_connection.publish(results, current_state["simulation_id"])

        elif gsy_e.constants.RETAIN_PAST_MARKET_STRATEGIES_STATE or self.export_results_on_finish:

            self._endpoint_buffer.update_coefficient_stats(
                area,
                current_state["sim_status"],
                progress_info,
                current_state,
                True,
                self._scm_manager,
            )
            self._update_area_stats(area, self._endpoint_buffer)

            if self.export_results_on_finish:
                assert self._export is not None
                if (
                    progress_info.current_slot_time is not None
                    and gsy_e.constants.RETAIN_PAST_MARKET_STRATEGIES_STATE
                ):
                    # for integration tests:
                    self._export.raw_data_to_json(
                        progress_info.current_slot_str,
                        self._endpoint_buffer.flattened_area_core_stats_dict,
                    )

                self._export.file_stats_endpoint(area, self._scm_manager)
