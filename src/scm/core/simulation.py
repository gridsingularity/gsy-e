from logging import getLogger
from time import sleep
from typing import Dict, Optional, TYPE_CHECKING

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import CoefficientAlgorithm, SCMSelfConsumptionType
from pendulum import Duration, duration

import gsy_e.constants
from gsy_e.gsy_e_core.global_objects_singleton import global_objects
from gsy_e.gsy_e_core.simulation.results_manager import (
    SimulationResultsManager,
)
from gsy_e.gsy_e_core.simulation.simulation import Simulation
from gsy_e.gsy_e_core.util import NonBlockingConsole
from scm.scm_manager import SCMManager, SCMManagerWithoutSurplusTrade
from gsy_e.models.config import SimulationConfig
from scm.core.results.results_manager import CoefficientSimulationResultsManager
from scm.core.time_manager import SimulationTimeManagerScm

if TYPE_CHECKING:
    from gsy_e.models.area.area_base import AreaBase
    from scm.coefficient_area import CoefficientArea

log = getLogger(__name__)


class CoefficientSimulation(Simulation):
    """Start and control a simulation with coefficient trading."""

    area: "CoefficientArea"
    _results: CoefficientSimulationResultsManager

    def __init__(
        self,
        setup_module_name: str,
        simulation_config: SimulationConfig,
        simulation_events: str = None,
        seed=None,
        paused: bool = False,
        pause_after: Duration = None,
        repl: bool = False,
        no_export: bool = False,
        export_path: str = None,
        export_subdir: str = None,
        redis_job_id=None,
        enable_bc=False,
        slot_length_realtime: Duration = None,
        incremental: bool = False,
        scm_properties: Optional[Dict] = None,
    ):
        # pylint: disable=too-many-arguments, too-many-locals

        # order matters here
        self._scm_properties = scm_properties if scm_properties is not None else {}
        super().__init__(
            setup_module_name,
            simulation_config,
            simulation_events,
            seed,
            paused,
            pause_after,
            repl,
            no_export,
            export_path,
            export_subdir,
            redis_job_id,
            enable_bc,
            slot_length_realtime,
            incremental,
        )

    @property
    def _results_manager_class(self):
        return SimulationResultsManager

    def _create_time_manager(self, slot_length_realtime, hours_of_delay):
        return SimulationTimeManagerScm(
            slot_length_realtime=slot_length_realtime, hours_of_delay=hours_of_delay
        )

    def update_scm_area_properties(self, area: "CoefficientArea"):
        """Update scm_properties for all non-asset areas."""
        area.update_area_properties(self._scm_properties)
        for child in area.children:
            if child.children is not None:
                self.update_scm_area_properties(child)

    def _init(self) -> None:
        # has to be called before load_setup_module():
        global_objects.profiles_handler.activate()

        self.area = self._setup.load_setup_module()

        self.update_scm_area_properties(self.area)

        # has to be called after areas are initiated in order to retrieve the profile uuids
        global_objects.profiles_handler.update_time_and_buffer_profiles(
            self._time.get_start_time_on_init(self.config), area=self.area
        )

        self._results.init_results(self.simulation_id, self.area, self._setup)
        self._results.update_and_send_results(self)

        log.debug("Starting simulation with config %s", self.config)

        self.area.activate_energy_parameters(self._time.get_start_time_on_init(self.config))

        if self.config.external_connection_enabled:
            global_objects.scm_external_global_stats(self.area)

    @property
    def _time_since_start(self) -> Duration:
        """Return pendulum duration since start of simulation."""
        current_time = (
            self.progress_info.current_slot_time
            if self.progress_info.current_slot_time
            else self.config.start_date
        )
        return current_time - self.config.start_date

    def _deactivate_areas(self, area: "AreaBase"):
        if area.strategy:
            area.strategy.deactivate()
        for child in area.children:
            self._deactivate_areas(child)

    def _handle_external_communication(self):
        if not self.config.external_connection_enabled:
            return

        global_objects.scm_external_global_stats.update()

        self.area.publish_market_cycle_to_external_clients()

        self.config.external_redis_communicator.approve_aggregator_commands()

        self.area.market_cycle_external()

        self.config.external_redis_communicator.publish_aggregator_commands_responses_events()

    def _cycle_markets(self, slot_no: int) -> None:
        # order matters here;
        # update of ProfilesHandler has to be called before cycle_coefficients_trading
        global_objects.profiles_handler.update_time_and_buffer_profiles(
            self._get_current_market_time_slot(slot_no), area=self.area
        )

        self.area.cycle_coefficients_trading(
            self.progress_info.current_slot_time,
            global_objects.profiles_handler.current_scm_profiles,
        )

    def _execute_scm_manager_cycle(self, slot_no: int) -> SCMManager:
        if (
            ConstSettings.SCMSettings.SELF_CONSUMPTION_TYPE
            == SCMSelfConsumptionType.SIMPLIFIED_COLLECTIVE_SELF_CONSUMPTION_41.value
        ):
            scm_manager = SCMManagerWithoutSurplusTrade(
                self.area, self._get_current_market_time_slot(slot_no)
            )
            production_kwh = self.area.aggregate_production_from_all_homes(
                self.progress_info.current_slot_time
            )
            self.area.calculate_home_after_meter_data_for_collective_self_consumption(
                self.progress_info.current_slot_time, scm_manager, production_kwh
            )
        else:
            scm_manager = SCMManager(self.area, self._get_current_market_time_slot(slot_no))
            self.area.calculate_home_after_meter_data(
                self.progress_info.current_slot_time, scm_manager
            )

        scm_manager.calculate_community_after_meter_data()
        self.area.trigger_energy_trades(scm_manager)
        scm_manager.accumulate_community_trades()

        if ConstSettings.SCMSettings.MARKET_ALGORITHM == CoefficientAlgorithm.DYNAMIC.value:
            self.area.change_home_coefficient_percentage(scm_manager)
        return scm_manager

    def _execute_simulation(
        self, slot_resume: int, _tick_resume: int, console: NonBlockingConsole = None
    ) -> None:
        slot_count, slot_resume = self._time.calc_resume_slot_and_count_realtime(
            self.config, slot_resume, self.status
        )

        self.config.external_redis_communicator.activate()

        self._time.reset(not_restored_from_state=slot_resume == 0)

        for slot_no in range(slot_resume, slot_count):
            self._handle_paused(console)

            self.progress_info.update(slot_no, slot_count, self._time, self.config)

            self._cycle_markets(slot_no)

            self._handle_external_communication()

            scm_manager = self._execute_scm_manager_cycle(slot_no)

            # important: SCM manager has to be updated before sending the results
            self._results.update_scm_manager(scm_manager)

            self._results.update_and_send_results(self)

            self._external_events.update(self.area)

            # self._compute_memory_info()

            self._time.handle_slowdown_and_realtime_scm(
                slot_no, slot_count, self.config, self.status
            )

            if self.status.stopped:
                log.error(
                    "Received stop command for configuration id %s and job id %s.",
                    gsy_e.constants.CONFIGURATION_ID,
                    self.simulation_id,
                )
                sleep(5)
                self._simulation_stopped_finish_actions(slot_count, status="stopped")
                return

            self._results.update_csv_files(
                slot_no, self.progress_info.current_slot_time, self.area, scm_manager
            )
            self.status.handle_incremental_mode()

        self._simulation_stopped_finish_actions(slot_count)

    def _simulation_stopped_finish_actions(self, slot_count: int, status="finished") -> None:
        self.status.sim_status = status
        self._deactivate_areas(self.area)
        self.config.external_redis_communicator.publish_aggregator_commands_responses_events()
        if not self.status.stopped:
            self.progress_info.update(slot_count - 1, slot_count, self._time, self.config)
            paused_duration = duration(seconds=self._time.paused_time)
            self.progress_info.log_simulation_finished(paused_duration, self.config)
        self._results.update_and_send_results(self)

        self._results.save_csv_results(self.area)
