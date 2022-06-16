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

import datetime
import gc
import os
import sys
from dataclasses import dataclass
from importlib import import_module
from logging import getLogger
from time import sleep, time, mktime
from types import ModuleType
from typing import Tuple, Optional, TYPE_CHECKING

import psutil
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.enums import SpotMarketTypeEnum
from gsy_framework.kafka_communication.kafka_producer import kafka_connection_factory
from gsy_framework.utils import format_datetime, str_to_pendulum_datetime
from numpy import random
from pendulum import now, duration, DateTime, Duration

import gsy_e.constants
from gsy_e.constants import TIME_ZONE, DATE_TIME_FORMAT, SIMULATION_PAUSE_TIMEOUT
from gsy_e.gsy_e_core.exceptions import SimulationException
from gsy_e.gsy_e_core.export import ExportAndPlot
from gsy_e.gsy_e_core.global_objects_singleton import global_objects
from gsy_e.gsy_e_core.live_events import LiveEvents
from gsy_e.gsy_e_core.myco_singleton import bid_offer_matcher
from gsy_e.gsy_e_core.redis_connections.simulation import RedisSimulationCommunication
from gsy_e.gsy_e_core.sim_results.endpoint_buffer import endpoint_buffer_class_factory
from gsy_e.gsy_e_core.sim_results.file_export_endpoints import FileExportEndpoints
from gsy_e.gsy_e_core.util import NonBlockingConsole, validate_const_settings_for_simulation
from gsy_e.models.area.event_deserializer import deserialize_events_to_areas
from gsy_e.models.area.scm_manager import SCMManager
from gsy_e.models.config import SimulationConfig

if TYPE_CHECKING:
    from gsy_e.models.area import Area, AreaBase
    from gsy_e.gsy_e_core.sim_results.endpoint_buffer import SimulationEndpointBuffer

log = getLogger(__name__)


RANDOM_SEED_MAX_VALUE = 1000000


class SimulationResetException(Exception):
    """Exception for errors when resetting the simulation."""


class SimulationProgressInfo:
    """Information about the simulation progress."""

    def __init__(self):
        self.eta = duration(seconds=0)
        self.elapsed_time = duration(seconds=0)
        self.percentage_completed = 0
        self.next_slot_str = ""
        self.current_slot_str = ""
        self.current_slot_time = None
        self.current_slot_number = 0

    @classmethod
    def _get_market_slot_time_str(cls, slot_number: int, config: "SimulationConfig") -> str:
        """Get market slot time string."""
        return format_datetime(cls._get_market_slot_time(slot_number, config))

    @staticmethod
    def _get_market_slot_time(slot_number: int, config: "SimulationConfig") -> DateTime:
        return config.start_date.add(
            minutes=config.slot_length.minutes * slot_number
        )

    def update(self, slot_no: int, slot_count: int, time_params: "SimulationTimeManager",
               config: SimulationConfig) -> None:
        """Update progress info according to the simulation progress."""
        run_duration = (
                now(tz=TIME_ZONE) - time_params.start_time -
                duration(seconds=time_params.paused_time)
        )

        if gsy_e.constants.RUN_IN_REALTIME:
            self.eta = None
            self.percentage_completed = 0.0
        else:
            self.eta = (run_duration / (slot_no + 1) * slot_count) - run_duration
            self.percentage_completed = (slot_no + 1) / slot_count * 100

        self.elapsed_time = run_duration
        self.current_slot_str = self._get_market_slot_time_str(slot_no, config)
        self.current_slot_time = self._get_market_slot_time(slot_no, config)
        self.next_slot_str = self._get_market_slot_time_str(
            slot_no + 1, config)
        self.current_slot_number = slot_no

        log.warning("Slot %s of %s - (%.1f %%) %s elapsed, ETA: %s", slot_no+1, slot_count,
                    self.percentage_completed, self.elapsed_time,
                    self.eta)

    def log_simulation_finished(self, paused_duration: Duration, config: SimulationConfig) -> None:
        """Log that the simulation has finished."""
        log.info(
            "Run finished in %s%s / %.2fx real time",
            self.elapsed_time,
            f" ({paused_duration} paused)" if paused_duration else "",
            config.sim_duration / (self.elapsed_time - paused_duration)
        )


@dataclass
class SimulationStatusManager:
    """State of the Simulation class."""
    paused: bool = False
    pause_after: duration = None
    timed_out: bool = False
    stopped: bool = False
    sim_status = "initializing"
    incremental: bool = False

    @property
    def status(self) -> str:
        """Return status of simulation."""
        if self.timed_out:
            return "timed-out"
        if self.stopped:
            return "stopped"
        if self.paused:
            return "paused"
        return self.sim_status

    def stop(self) -> None:
        """Stop simulation."""
        self.stopped = True

    @property
    def finished(self) -> bool:
        """Return if simulation has finished."""
        return self.sim_status == "finished"

    def toggle_pause(self) -> bool:
        """Pause or resume simulation."""
        if self.finished:
            return False
        self.paused = not self.paused
        return True

    def handle_pause_after(self, time_since_start: Duration) -> None:
        """Deals with pause-after parameter, which pauses the simulation after some time."""
        if self.pause_after and time_since_start >= self.pause_after:
            self.paused = True
            self.pause_after = None

    def handle_pause_timeout(self, tick_time_counter: float) -> None:
        """
        Deals with the case that the pause time exceeds the simulation timeout, in which case the
        simulation should be stopped.
        """
        if time() - tick_time_counter > SIMULATION_PAUSE_TIMEOUT:
            self.timed_out = True
            self.stopped = True
            self.paused = False
        if self.stopped:
            self.paused = False

    def handle_incremental_mode(self) -> None:
        """
        Handle incremental paused mode, where simulation is paused after each market slot.
        """
        if self.incremental:
            self.paused = True


@dataclass
class SimulationTimeManager:
    """Handles simulation time management."""
    start_time: DateTime = now(tz=TIME_ZONE)
    tick_time_counter: float = time()
    slot_length_realtime: duration = None
    tick_length_realtime_s: int = None
    paused_time: int = 0  # Time spent in paused state, in seconds

    def reset(self, not_restored_from_state: bool = True) -> None:
        """
        Restore time-related parameters of the simulation to their default values.
        Mainly useful when resetting the simulation.
        """
        self.tick_time_counter = time()
        if not_restored_from_state:
            self.start_time = now(tz=TIME_ZONE)
            self.paused_time = 0

    def _set_area_current_tick(self, area: "Area", current_tick: int) -> None:
        area.current_tick = current_tick
        for child in area.children:
            self._set_area_current_tick(child, current_tick)

    def calculate_total_initial_ticks_slots(
            self, config: SimulationConfig, slot_resume: int, tick_resume: int, area: "Area"
    ) -> Tuple[int, int, int]:
        """Calculate the initial slot and tick of the simulation, and the total slot count."""
        slot_count = int(config.sim_duration / config.slot_length)

        if gsy_e.constants.RUN_IN_REALTIME:
            slot_count = sys.maxsize

            today = datetime.date.today()
            seconds_since_midnight = time() - mktime(today.timetuple())
            slot_resume = int(seconds_since_midnight // config.slot_length.seconds) + 1
            seconds_elapsed_in_slot = seconds_since_midnight % config.slot_length.seconds
            ticks_elapsed_in_slot = seconds_elapsed_in_slot // config.tick_length.seconds
            tick_resume = int(ticks_elapsed_in_slot) + 1

            seconds_elapsed_in_tick = seconds_elapsed_in_slot % config.tick_length.seconds

            seconds_until_next_tick = config.tick_length.seconds - seconds_elapsed_in_tick

            ticks_since_midnight = int(seconds_since_midnight // config.tick_length.seconds) + 1
            self._set_area_current_tick(area, ticks_since_midnight)

            sleep(seconds_until_next_tick)

        if self.slot_length_realtime:
            self.tick_length_realtime_s = (
                    self.slot_length_realtime.seconds /
                    config.ticks_per_slot)
        return slot_count, slot_resume, tick_resume

    def handle_slowdown_and_realtime(self, tick_no: int, config: SimulationConfig) -> None:
        """
        Handle simulation slowdown and simulation realtime mode, and sleep the simulation
        accordingly.
        """
        if gsy_e.constants.RUN_IN_REALTIME:
            tick_runtime_s = time() - self.tick_time_counter
            sleep(abs(config.tick_length.seconds - tick_runtime_s))
        elif self.slot_length_realtime:
            current_expected_tick_time = self.tick_time_counter + self.tick_length_realtime_s
            sleep_time_s = current_expected_tick_time - now().timestamp()
            if sleep_time_s > 0:
                sleep(sleep_time_s)
                log.debug("Tick %s/%s: Sleep time of %s s was applied",
                          tick_no + 1, config.ticks_per_slot, sleep_time_s)

        self.tick_time_counter = time()


@dataclass
class SimulationSetup:
    """Static simulation configuration."""
    seed: int = 0
    enable_bc: bool = False
    use_repl: bool = False
    setup_module_name: str = ""
    started_from_cli: str = True
    config: SimulationConfig = None

    def __post_init__(self) -> None:
        self._set_random_seed(self.seed)

    def load_setup_module(self) -> "Area":
        """Load setup module and create areas that are described on the setup."""
        loaded_python_module = self._import_setup_module(self.setup_module_name)
        area = loaded_python_module.get_setup(self.config)
        self._log_traversal_length(area)
        return area

    def _set_random_seed(self, seed: Optional[int]) -> None:
        if seed is not None:
            random.seed(int(seed))
        else:
            random_seed = random.randint(0, RANDOM_SEED_MAX_VALUE)
            random.seed(random_seed)
            seed = random_seed
            log.info("Random seed: %s", random_seed)
        self.seed = seed

    def _log_traversal_length(self, area: "Area") -> None:
        no_of_levels = self._get_setup_levels(area) + 1
        num_ticks_to_propagate = no_of_levels * 2
        time_to_propagate_minutes = (num_ticks_to_propagate *
                                     self.config.tick_length.seconds / 60.)
        log.info("Setup has %s levels, offers/bids need at least %s minutes to propagate.",
                 no_of_levels, time_to_propagate_minutes)

    def _get_setup_levels(self, area: "Area", level_count: int = 0) -> int:
        level_count += 1
        count_list = [self._get_setup_levels(child, level_count)
                      for child in area.children if child.children]
        return max(count_list) if len(count_list) > 0 else level_count

    @staticmethod
    def _import_setup_module(setup_module_name: str) -> ModuleType:
        try:
            if ConstSettings.GeneralSettings.SETUP_FILE_PATH is None:
                return import_module(f".{setup_module_name}", "gsy_e.setup")
            sys.path.append(ConstSettings.GeneralSettings.SETUP_FILE_PATH)
            return import_module(f"{setup_module_name}")
        except (ModuleNotFoundError, ImportError) as ex:
            raise SimulationException(
                f"Invalid setup module '{setup_module_name}'") from ex
        finally:
            log.debug("Using setup module '%s'", setup_module_name)


class SimulationResultsManager:
    """Maintain and populate the simulation results and the publishing to the message broker."""
    def __init__(self, export_results_on_finish: bool, export_path: str,
                 export_subdir: Optional[str], started_from_cli: bool) -> None:
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

    def init_results(self, redis_job_id: str, area: "Area",
                     config_params: SimulationSetup) -> None:
        """Construct objects that contain the simulation results for the broker and CSV output."""
        self._endpoint_buffer = endpoint_buffer_class_factory()(
            redis_job_id, config_params.seed,
            area, self.export_results_on_finish)

        if self.export_results_on_finish:
            self._export = ExportAndPlot(area, self.export_path,
                                         self.export_subdir,
                                         FileExportEndpoints(), self._endpoint_buffer)

    @property
    def _should_send_results_to_broker(self) -> None:
        """Flag that decides whether to send results to the gsy-web"""
        return not self.started_from_cli and self.kafka_connection.is_enabled()

    def update_and_send_results(self, current_state: dict, progress_info: SimulationProgressInfo,
                                area: "Area", simulation_status: str) -> None:
        """
        Update the simulation results. Should be called on init, finish and every market cycle.
        """
        assert self._endpoint_buffer is not None

        if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.COEFFICIENTS.value:
            if not self._should_send_results_to_broker:
                return
            self._endpoint_buffer.update_stats(
                area, simulation_status, progress_info, current_state,
                calculate_results=False)

            results = self._endpoint_buffer.prepare_results_for_publish()
            if results is None:
                return
            self.kafka_connection.publish(results, current_state["simulation_id"])
            return

        if self._should_send_results_to_broker:
            self._endpoint_buffer.update_stats(
                area, simulation_status, progress_info, current_state,
                calculate_results=False)
            results = self._endpoint_buffer.prepare_results_for_publish()
            if results is None:
                return
            self.kafka_connection.publish(results, current_state["simulation_id"])

        elif (gsy_e.constants.RETAIN_PAST_MARKET_STRATEGIES_STATE or
                self.export_results_on_finish):

            self._endpoint_buffer.update_stats(
                area, current_state["sim_status"], progress_info, current_state,
                calculate_results=True)
            self._update_area_stats(area, self._endpoint_buffer)

            if self.export_results_on_finish:
                assert self._export is not None
                if (area.current_market is not None
                        and gsy_e.constants.RETAIN_PAST_MARKET_STRATEGIES_STATE):
                    # for integration tests:
                    self._export.raw_data_to_json(
                        area.current_market.time_slot_str,
                        self._endpoint_buffer.flattened_area_core_stats_dict
                    )

                self._export.file_stats_endpoint(area)

    @classmethod
    def _update_area_stats(cls, area: "Area", endpoint_buffer: "SimulationEndpointBuffer") -> None:
        # TODO: Fix in the context of GSYE-258
        if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.COEFFICIENTS.value:
            return
        for child in area.children:
            cls._update_area_stats(child, endpoint_buffer)
        bills = endpoint_buffer.results_handler.all_ui_results["bills"].get(area.uuid, {})
        area.stats.update_aggregated_stats({"bills": bills})
        area.stats.kpi.update(
            endpoint_buffer.results_handler.all_ui_results["kpi"].get(area.uuid, {}))

    def update_csv_on_market_cycle(self, slot_no: int, area: "Area") -> None:
        """Update the csv results on market cycle."""
        if self.export_results_on_finish:
            self._export.data_to_csv(area, slot_no == 0)

    def save_csv_results(self, area: "Area") -> None:
        """Update the CSV results on finish, and write the CSV files."""
        # TODO: Fix with GSYE-258
        if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.COEFFICIENTS.value:
            return
        if self.export_results_on_finish:
            log.info("Exporting simulation data.")
            self._export.data_to_csv(area, False)
            self._export.area_tree_summary_to_json(self._endpoint_buffer.area_result_dict)
            self._export.export(power_flow=None)


class SimulationExternalEvents:
    """
    Handle signals that affect the simulation state, that arrive from Redis. Consists of live
    events and signals that change the simulation status.
    """
    def __init__(self, simulation_id: str, config: SimulationConfig,
                 state_params: SimulationStatusManager, progress_info: SimulationProgressInfo,
                 area: "Area") -> None:
        # pylint: disable=too-many-arguments
        self.live_events = LiveEvents(config)
        self.redis_connection = RedisSimulationCommunication(
            state_params, simulation_id, self.live_events, progress_info, area)

    def update(self, area: "Area") -> None:
        """
        Update the simulation according to any live events received. Triggered every market slot.
        """
        self.live_events.handle_all_events(area)


class Simulation:
    """Main class that starts and controls simulation."""
    # pylint: disable=too-many-arguments,too-many-instance-attributes
    def __init__(self, setup_module_name: str, simulation_config: SimulationConfig,
                 simulation_events: str = None, seed=None,
                 paused: bool = False, pause_after: Duration = None, repl: bool = False,
                 no_export: bool = False, export_path: str = None,
                 export_subdir: str = None, redis_job_id=None, enable_bc=False,
                 slot_length_realtime: Duration = None, incremental: bool = False):
        self._status = SimulationStatusManager(
            paused=paused,
            pause_after=pause_after,
            incremental=incremental
        )
        self._time = SimulationTimeManager(
            slot_length_realtime=slot_length_realtime,
        )

        self._setup = SimulationSetup(
            seed=seed,
            enable_bc=enable_bc,
            use_repl=repl,
            setup_module_name=setup_module_name,
            started_from_cli=redis_job_id is None,
            config=simulation_config
        )

        self._results = SimulationResultsManager(
            export_results_on_finish=not no_export,
            export_path=export_path,
            export_subdir=export_subdir,
            started_from_cli=redis_job_id is None
        )

        self.progress_info = SimulationProgressInfo()
        self._simulation_id = redis_job_id

        self._init(redis_job_id)

        self._external_events = SimulationExternalEvents(
            redis_job_id, self._setup.config, self._status, self.progress_info, self.area)

        deserialize_events_to_areas(simulation_events, self.area)

        validate_const_settings_for_simulation()

    def _init(self, redis_job_id: str) -> None:
        # has to be called before get_setup():
        global_objects.profiles_handler.activate()

        self.area = self._setup.load_setup_module()
        bid_offer_matcher.activate()
        global_objects.external_global_stats(self.area, self._setup.config.ticks_per_slot)

        self._results.init_results(redis_job_id, self.area, self._setup)
        self._results.update_and_send_results(
            self.current_state, self.progress_info, self.area, self._status.status)

        log.debug("Starting simulation with config %s", self._setup.config)

        self.area.activate(self._setup.enable_bc, simulation_id=redis_job_id)

    @property
    def _time_since_start(self) -> Duration:
        """Return pendulum duration since start of simulation."""
        return self.area.current_tick * self._setup.config.tick_length

    def reset(self) -> None:
        """
        Reset simulation to initial values and restart the run.
        """
        log.info("%s Simulation reset requested %s", "=" * 15, "=" * 15)
        self._init(self._simulation_id)
        self.run()
        raise SimulationResetException

    def _deactivate_areas(self, area: "Area") -> None:
        """Move the last market into area.past_markets."""
        area.deactivate()
        for child in area.children:
            self._deactivate_areas(child)

    def run(self, initial_slot: int = 0) -> None:
        """Run the simulation."""
        self._status.sim_status = "running"
        self._status.stopped = False

        self._time.reset(
            not_restored_from_state=(initial_slot == 0)
        )

        tick_resume = 0
        try:
            if self._setup.started_from_cli:
                self._run_cli_execute_cycle(initial_slot, tick_resume)
            else:
                self._execute_simulation(initial_slot, tick_resume)
        except (KeyboardInterrupt, SimulationResetException):
            pass

    def _run_cli_execute_cycle(self, slot_resume: int, tick_resume: int) -> None:
        with NonBlockingConsole() as console:
            self._execute_simulation(slot_resume, tick_resume, console)

    def _get_current_market_time_slot(self, slot_number: int) -> DateTime:
        return (self.area.config.start_date + (slot_number * self.area.config.slot_length)
                if GlobalConfig.IS_CANARY_NETWORK else self.area.now)

    def _execute_simulation(
            self, slot_resume: int, tick_resume: int, console: NonBlockingConsole = None) -> None:
        slot_count, slot_resume, tick_resume = (
            self._time.calculate_total_initial_ticks_slots(
                self._setup.config, slot_resume, tick_resume, self.area))

        self._setup.config.external_redis_communicator.sub_to_aggregator()
        self._setup.config.external_redis_communicator.start_communication()

        for slot_no in range(slot_resume, slot_count):
            self.progress_info.update(
                slot_no, slot_count, self._time, self._setup.config)

            self.area.cycle_markets()

            global_objects.profiles_handler.update_time_and_buffer_profiles(
                self._get_current_market_time_slot(slot_no))

            if self._setup.config.external_connection_enabled:
                global_objects.external_global_stats.update(market_cycle=True)
                self.area.publish_market_cycle_to_external_clients()

            bid_offer_matcher.event_market_cycle(
                slot_completion="0%",
                market_slot=self.progress_info.current_slot_str)

            self._results.update_and_send_results(
                self.current_state, self.progress_info, self.area, self._status.status)
            self._external_events.update(self.area)

            gc.collect()
            process = psutil.Process(os.getpid())
            mbs_used = process.memory_info().rss / 1000000.0
            log.debug("Used %s MBs.", mbs_used)

            for tick_no in range(tick_resume, self._setup.config.ticks_per_slot):
                self._handle_paused(console)

                # reset tick_resume after possible resume
                tick_resume = 0
                log.trace("Tick %s of %s in slot %s (%.1f%)", tick_no + 1,
                          self._setup.config.ticks_per_slot,
                          slot_no + 1, (tick_no + 1) / self._setup.config.ticks_per_slot * 100)

                self._setup.config.external_redis_communicator.\
                    approve_aggregator_commands()

                current_tick_in_slot = tick_no % self._setup.config.ticks_per_slot
                if (self._setup.config.external_connection_enabled and
                        global_objects.external_global_stats.is_it_time_for_external_tick(
                            current_tick_in_slot)):
                    global_objects.external_global_stats.update()

                self.area.tick_and_dispatch()
                self.area.execute_actions_after_tick_event()
                bid_offer_matcher.event_tick(
                    current_tick_in_slot=current_tick_in_slot,
                    slot_completion=f"{int((tick_no / self._setup.config.ticks_per_slot) * 100)}%",
                    market_slot=self.progress_info.next_slot_str)
                self._setup.config.external_redis_communicator.\
                    publish_aggregator_commands_responses_events()

                self._time.handle_slowdown_and_realtime(tick_no, self._setup.config)

                if self._status.stopped:
                    log.error("Received stop command for configuration id %s and job id %s.",
                              gsy_e.constants.CONFIGURATION_ID, self._simulation_id)
                    sleep(5)
                    self._simulation_finish_actions(slot_count)
                    return

            self._results.update_csv_on_market_cycle(slot_no, self.area)
            self._status.handle_incremental_mode()
        self._simulation_finish_actions(slot_count)

    def _simulation_finish_actions(self, slot_count: int) -> None:
        self._status.sim_status = "finished"
        self._deactivate_areas(self.area)
        self._setup.config.external_redis_communicator.\
            publish_aggregator_commands_responses_events()
        bid_offer_matcher.event_finish()
        if not self._status.stopped:
            self.progress_info.update(
                slot_count - 1, slot_count, self._time, self._setup.config)
            paused_duration = duration(seconds=self._time.paused_time)
            self.progress_info.log_simulation_finished(paused_duration, self._setup.config)
        self._results.update_and_send_results(
            self.current_state, self.progress_info, self.area, self._status.status)
        self._results.save_csv_results(self.area)

    def _handle_input(self, console: NonBlockingConsole, sleep_period: float = 0) -> None:
        timeout = 0
        start = 0
        if sleep_period > 0:
            timeout = sleep_period / 100
            start = time()
        while True:
            cmd = console.get_char(timeout)
            if cmd:
                if cmd not in {"i", "p", "q", "r", "R", "s", "+", "-"}:
                    log.critical("Invalid command. Valid commands:\n"
                                 "  [i] info\n"
                                 "  [p] pause\n"
                                 "  [q] quit\n"
                                 "  [r] reset\n"
                                 "  [s] stop\n"
                                 "  [R] start REPL\n")
                    continue

                if self._status.finished and cmd in {"p", "+", "-"}:
                    log.info("Simulation has finished. The commands [p, +, -] are unavailable.")
                    continue

                if cmd == "r":
                    self.reset()
                elif cmd == "i":
                    self._info()
                elif cmd == "p":
                    self._status.toggle_pause()
                    break
                elif cmd == "q":
                    raise KeyboardInterrupt()
                elif cmd == "s":
                    self._status.stop()

            if sleep_period == 0 or time() - start >= sleep_period:
                break

    def _handle_paused(self, console: NonBlockingConsole) -> None:
        if console is not None:
            self._handle_input(console)
            self._status.handle_pause_after(self._time_since_start)
        paused_flag = False
        if self._status.paused:
            if console:
                log.critical("Simulation paused. Press 'p' to resume or resume from API.")
            else:
                self._results.update_and_send_results(
                    self.current_state, self.progress_info, self.area, self._status.status)
            start = time()
        while self._status.paused:
            paused_flag = True
            if console:
                self._handle_input(console, 0.1)
                self._status.handle_pause_timeout(self._time.tick_time_counter)
            sleep(0.5)

        if console and paused_flag:
            log.critical("Simulation resumed")
            self._time.paused_time += time() - start

    def _info(self) -> None:
        info = self._setup.config.as_dict()
        slot, tick = divmod(self.area.current_tick, self._setup.config.ticks_per_slot)
        percent = self.area.current_tick / self._setup.config.total_ticks * 100
        slot_count = self._setup.config.sim_duration // self._setup.config.slot_length
        info.update(slot=slot + 1, tick=tick + 1, slot_count=slot_count, percent=percent)
        log.critical(
            "\n"
            "Simulation configuration:\n"
            "  Duration: %(sim_duration)s\n"
            "  Slot length: %(slot_length)s\n"
            "  Tick length: %(tick_length)s\n"
            "  Ticks per slot: %(ticks_per_slot)d\n"
            "Status:\n"
            "  Slot: %(slot)d / %(slot_count)d\n"
            "  Tick: %(tick)d / %(ticks_per_slot)d\n"
            "  Completed: %(percent).1f%%",
            info
        )

    @property
    def current_state(self) -> dict:
        """Return dict that contains current progress and state of simulation."""
        return {
            "paused": self._status.paused,
            "seed": self._setup.seed,
            "sim_status": self._status.sim_status,
            "stopped": self._status.stopped,
            "simulation_id": self._simulation_id,
            "run_start": format_datetime(self._time.start_time)
            if self._time.start_time is not None else "",
            "paused_time": self._time.paused_time,
            "slot_number": self.progress_info.current_slot_number,
            "slot_length_realtime_s": str(self._time.slot_length_realtime.seconds)
            if self._time.slot_length_realtime else 0
        }

    def _restore_area_state(self, area: "Area", saved_area_state: dict) -> None:
        if area.uuid not in saved_area_state:
            log.warning("Area %s is not part of the saved state. State not restored. "
                        "Simulation id: %s", area.uuid, self._simulation_id)
        else:
            area.restore_state(saved_area_state[area.uuid])
        for child in area.children:
            self._restore_area_state(child, saved_area_state)

    def restore_area_state_all_areas(self, saved_area_state: dict) -> None:
        """Restore state of all areas."""
        self._restore_area_state(self.area, saved_area_state)

    def restore_global_state(self, saved_state: dict) -> None:
        """Restore global state of simulation."""
        self._status.paused = saved_state["paused"]
        self._setup.seed = saved_state["seed"]
        self._status.sim_status = saved_state["sim_status"]
        self._status.stopped = saved_state["stopped"]
        self._simulation_id = saved_state["simulation_id"]
        if saved_state["run_start"] != "":
            self._time.start_time = str_to_pendulum_datetime(saved_state["run_start"])
        self._time.paused_time = saved_state["paused_time"]
        self.progress_info.current_slot_number = saved_state["slot_number"]
        self._time.slot_length_realtime = duration(
            seconds=saved_state["slot_length_realtime_s"])


class CoefficientSimulation(Simulation):
    """Start and control a simulation with coefficient trading."""

    def _init(self, redis_job_id: str) -> None:
        # has to be called before get_setup():
        global_objects.profiles_handler.activate()

        self.area = self._setup.load_setup_module()
        bid_offer_matcher.activate()

        self._results.init_results(redis_job_id, self.area, self._setup)
        self._results.update_and_send_results(
            self.current_state, self.progress_info, self.area, self._status.status)

        log.debug("Starting simulation with config %s", self._setup.config)

        self.area.activate_coefficients(self._setup.config.start_date)

    @property
    def _time_since_start(self) -> Duration:
        """Return pendulum duration since start of simulation."""
        current_time = self.progress_info.current_slot_time \
            if self.progress_info.current_slot_time else self._setup.config.start_date
        return current_time - self._setup.config.start_date

    def _deactivate_areas(self, area: "AreaBase"):
        pass

    def _execute_simulation(
            self, slot_resume: int, tick_resume: int, console: NonBlockingConsole = None) -> None:

        slot_count, slot_resume, tick_resume = (
            self._time.calculate_total_initial_ticks_slots(
                self._setup.config, slot_resume, tick_resume, self.area))

        for slot_no in range(slot_resume, slot_count):
            self._handle_paused(console)

            self.progress_info.update(slot_no, slot_count, self._time, self._setup.config)

            self.area.cycle_coefficients_trading(self.progress_info.current_slot_time)

            global_objects.profiles_handler.update_time_and_buffer_profiles(
                self._get_current_market_time_slot(slot_no))

            scm_manager = SCMManager(self.area.uuid, self._get_current_market_time_slot(slot_no))

            self.area.calculate_home_after_meter_data(
                self.progress_info.current_slot_time, scm_manager)

            scm_manager.calculate_community_after_meter_data()
            self.area.trigger_energy_trades(scm_manager)

            self._results.update_and_send_results(
                self.current_state, self.progress_info, self.area, self._status.status)
            self._external_events.update(self.area)

            gc.collect()
            process = psutil.Process(os.getpid())
            mbs_used = process.memory_info().rss / 1000000.0
            log.debug("Used %s MBs.", mbs_used)

            self._time.handle_slowdown_and_realtime(0, self._setup.config)

            if self._status.stopped:
                log.error("Received stop command for configuration id %s and job id %s.",
                          gsy_e.constants.CONFIGURATION_ID, self._simulation_id)
                sleep(5)
                self._simulation_finish_actions(slot_count)
                return

            # self._results.update_csv_on_market_cycle(slot_no, self.area)
            self._status.handle_incremental_mode()

        self._simulation_finish_actions(slot_count)


def simulation_class_factory():
    """
    Factory method that selects the correct simulation class for market or coefficient trading.
    """
    return (
        CoefficientSimulation
        if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.COEFFICIENTS.value
        else Simulation
    )


def run_simulation(setup_module_name: str = "", simulation_config: SimulationConfig = None,
                   simulation_events: str = None,
                   redis_job_id: str = None, saved_sim_state: dict = None,
                   slot_length_realtime: Duration = None, kwargs: dict = None) -> None:
    """Initiate simulation class and start simulation."""
    # pylint: disable=too-many-arguments
    try:
        if "pricing_scheme" in kwargs:
            ConstSettings.MASettings.AlternativePricing.PRICING_SCHEME = (
                kwargs.pop("pricing_scheme"))

        if saved_sim_state is None:
            simulation = simulation_class_factory()(
                setup_module_name=setup_module_name,
                simulation_config=simulation_config,
                simulation_events=simulation_events,
                slot_length_realtime=slot_length_realtime,
                redis_job_id=redis_job_id,
                **kwargs
            )
        else:
            simulation = simulation_class_factory()(
                setup_module_name=setup_module_name,
                simulation_config=simulation_config,
                simulation_events=simulation_events,
                slot_length_realtime=slot_length_realtime,
                redis_job_id=saved_sim_state["general"]["simulation_id"],
                **kwargs
            )
    except SimulationException as ex:
        log.error(ex)
        return

    if (saved_sim_state is not None and
            saved_sim_state["areas"] != {} and
            saved_sim_state["general"]["sim_status"] in ["running", "paused"]):
        simulation.restore_global_state(saved_sim_state["general"])
        simulation.restore_area_state_all_areas(saved_sim_state["areas"])
        simulation.run(initial_slot=saved_sim_state["general"]["slot_number"])
    else:
        simulation.run()
