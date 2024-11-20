from typing import TYPE_CHECKING, Dict

from gsy_framework.sim_results.all_results import SCMResultsHandler

from gsy_e.gsy_e_core.sim_results.endpoint_buffer import (
    SimulationEndpointBuffer,
    SimulationResultValidator,
)
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.finite_power_plant import FinitePowerPlant

if TYPE_CHECKING:
    from gsy_e.gsy_e_core.simulation import SimulationProgressInfo
    from gsy_e.models.area import AreaBase
    from gsy_e.models.area.scm_manager import SCMManager


class CoefficientEndpointBuffer(SimulationEndpointBuffer):
    """Calculate the endpoint results for the Coefficient based market."""

    def __init__(self, *args, **kwargs):
        self._scm_past_slots = kwargs.pop("scm_past_slots", False)
        super().__init__(*args, **kwargs)
        self._scm_manager = None

    def _generate_result_report(self) -> Dict:
        """Create dict that contains all statistics that are sent to the gsy-web."""
        result_dict = super()._generate_result_report()
        return {"scm_past_slots": self._scm_past_slots, **result_dict}

    def update_coefficient_stats(  # pylint: disable=too-many-arguments
        self,
        area: "AreaBase",
        simulation_status: str,
        progress_info: "SimulationProgressInfo",
        sim_state: Dict,
        calculate_results: bool,
        scm_manager: "SCMManager",
    ) -> None:
        """Update the stats of the SCM endpoint buffer."""
        self._scm_manager = scm_manager

        self.spot_market_time_slot_str = progress_info.current_slot_str
        if progress_info.current_slot_time:
            self.spot_market_time_slot = progress_info.current_slot_time
            self.spot_market_time_slot_unix = progress_info.current_slot_time.timestamp()

        super().update_stats(area, simulation_status, progress_info, sim_state, calculate_results)

    def _create_results_validator(self):
        self.results_validator = SimulationResultValidator(is_scm=True)

    @staticmethod
    def _create_results_handler(_should_export_plots):
        return SCMResultsHandler()

    def _calculate_and_update_last_market_time_slot(self, area):
        pass

    def _populate_core_stats_and_sim_state(self, area: "AreaBase"):
        if area.uuid not in self.flattened_area_core_stats_dict:
            self.flattened_area_core_stats_dict[area.uuid] = {}
        if self.spot_market_time_slot_str == "":
            return

        core_stats_dict = {}

        if isinstance(area.strategy, CommercialStrategy):
            if isinstance(area.strategy, FinitePowerPlant):
                core_stats_dict["production_kWh"] = area.strategy.energy_per_slot_kWh
            else:
                if area.parent.spot_market is not None:
                    core_stats_dict["energy_rate"] = area.strategy.energy_rate.get(area.now, None)
        elif not area.strategy and self._scm_manager is not None:
            core_stats_dict.update(
                self._scm_manager.get_area_results(area.uuid, serializable=True)
            )
        else:
            core_stats_dict.update(area.get_results_dict())

        self.flattened_area_core_stats_dict[area.uuid] = core_stats_dict

        self.simulation_state["areas"][area.uuid] = area.get_state()

        for child in area.children:
            self._populate_core_stats_and_sim_state(child)
