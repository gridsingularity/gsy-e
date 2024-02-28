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

import gc
import os
from logging import getLogger
from time import sleep, time
from typing import TYPE_CHECKING, Dict

import psutil
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.enums import CoefficientAlgorithm, SpotMarketTypeEnum
from gsy_framework.utils import format_datetime, str_to_pendulum_datetime
from pendulum import DateTime, Duration, duration

import gsy_e.constants
from gsy_e.gsy_e_core.exceptions import SimulationException
from gsy_e.gsy_e_core.global_objects_singleton import global_objects
from gsy_e.gsy_e_core.matching_engine_singleton import bid_offer_matcher
from gsy_e.gsy_e_core.simulation.external_events import SimulationExternalEvents
from gsy_e.gsy_e_core.simulation.progress_info import SimulationProgressInfo
from gsy_e.gsy_e_core.simulation.results_manager import (
    simulation_results_manager_factory, CoefficientSimulationResultsManager)
from gsy_e.gsy_e_core.simulation.setup import SimulationSetup
from gsy_e.gsy_e_core.simulation.status_manager import SimulationStatusManager
from gsy_e.gsy_e_core.simulation.time_manager import (
    simulation_time_manager_factory)
from gsy_e.gsy_e_core.util import NonBlockingConsole
from gsy_e.models.area.event_deserializer import deserialize_events_to_areas
from gsy_e.models.area.scm_manager import SCMManager
from gsy_e.models.config import SimulationConfig

if TYPE_CHECKING:
    from gsy_e.models.area import Area, AreaBase, CoefficientArea

log = getLogger(__name__)


class SimulationResetException(Exception):
    """Exception for errors when resetting the simulation."""


class Simulation:
    """Main class that starts and controls simulation."""
    # pylint: disable=too-many-arguments,too-many-instance-attributes
    def __init__(self, setup_module_name: str, simulation_config: SimulationConfig,
                 simulation_events: str = None, seed=None,
                 paused: bool = False, pause_after: Duration = None, repl: bool = False,
                 no_export: bool = False, export_path: str = None,
                 export_subdir: str = None, redis_job_id=None, enable_bc=False,
                 slot_length_realtime: Duration = None, incremental: bool = False):
        self.status = SimulationStatusManager(
            paused=paused,
            pause_after=pause_after,
            incremental=incremental
        )
        self._time = simulation_time_manager_factory(
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

        self._results = simulation_results_manager_factory()(
            export_results_on_finish=not no_export,
            export_path=export_path,
            export_subdir=export_subdir,
            started_from_cli=redis_job_id is None
        )

        self.area = None
        self.progress_info = SimulationProgressInfo()
        self.simulation_id = redis_job_id

        # order matters here: self.area has to be not-None before _external_events are initiated
        self._init()
        self._external_events = SimulationExternalEvents(self)

        deserialize_events_to_areas(simulation_events, self.area)

    def _init(self) -> None:
        # has to be called before load_setup_module():
        global_objects.profiles_handler.activate()

        self.area = self._setup.load_setup_module()

        # has to be called after areas are initiated in order to retrieve the profile uuids
        global_objects.profiles_handler.update_time_and_buffer_profiles(
            GlobalConfig.start_date, area=self.area)

        bid_offer_matcher.activate()
        global_objects.external_global_stats(self.area, self.config.ticks_per_slot)

        self._results.init_results(self.simulation_id, self.area, self._setup)
        self._results.update_and_send_results(simulation=self)

        log.debug("Starting simulation with config %s", self.config)

        self.area.activate(self._setup.enable_bc, simulation_id=self.simulation_id)

    @property
    def config(self) -> SimulationConfig:
        """Return the configuration of the simulation."""
        return self._setup.config

    @property
    def _time_since_start(self) -> Duration:
        """Return pendulum duration since start of simulation."""
        return self.area.current_tick * self.config.tick_length

    def reset(self) -> None:
        """
        Reset simulation to initial values and restart the run.
        """
        log.info("%s Simulation reset requested %s", "=" * 15, "=" * 15)
        self._init()
        self.run()
        raise SimulationResetException

    def _deactivate_areas(self, area: "Area") -> None:
        """Move the last market into area.past_markets."""
        area.deactivate()
        for child in area.children:
            self._deactivate_areas(child)

    def run(self, initial_slot: int = 0) -> None:
        """Run the simulation."""
        self.status.sim_status = "running"
        self.status.stopped = False

        self._time.reset(
            not_restored_from_state=(initial_slot == 0)
        )

        tick_resume = 0
        try:
            if self._setup.started_from_cli:
                self._run_cli_execute_cycle(initial_slot, tick_resume)
            else:
                # update status of the simulation before executing it.
                self._results.update_and_send_results(simulation=self)
                self._execute_simulation(initial_slot, tick_resume)
        except (KeyboardInterrupt, SimulationResetException):
            pass

    def _run_cli_execute_cycle(self, slot_resume: int, tick_resume: int) -> None:
        with NonBlockingConsole() as console:
            self._execute_simulation(slot_resume, tick_resume, console)

    def _get_current_market_time_slot(self, slot_number: int) -> DateTime:
        return (self.area.config.start_date + (slot_number * self.area.config.slot_length)
                if GlobalConfig.is_canary_network() else self.area.now)

    def _cycle_markets(self, slot_no: int) -> None:
        # order matters here;
        # update of ProfilesHandler has to be called before cycle_markets
        global_objects.profiles_handler.update_time_and_buffer_profiles(
            self._get_current_market_time_slot(slot_no), area=self.area)

        self.area.cycle_markets()

    def _execute_simulation(
            self, slot_resume: int, tick_resume: int, console: NonBlockingConsole = None) -> None:
        slot_count, slot_resume, tick_resume = (
            self._time.calculate_total_initial_ticks_slots(
                self.config, slot_resume, tick_resume, self.area, self.status))

        self.config.external_redis_communicator.activate()

        for slot_no in range(slot_resume, slot_count):
            self.progress_info.update(
                slot_no, slot_count, self._time, self.config)

            self._cycle_markets(slot_no)

            if self.config.external_connection_enabled:
                global_objects.external_global_stats.update(market_cycle=True)
                self.area.publish_market_cycle_to_external_clients()

            bid_offer_matcher.event_market_cycle(
                slot_completion="0%",
                market_slot=self.progress_info.current_slot_str)

            self._external_events.update(self.area)

            self._compute_memory_info()

            for tick_no in range(tick_resume, self.config.ticks_per_slot):
                self._handle_paused(console)

                # reset tick_resume after possible resume
                tick_resume = 0
                log.trace("Tick %s of %s in slot %s (%.1f%%)", tick_no + 1,
                          self.config.ticks_per_slot,
                          slot_no + 1, (tick_no + 1) / self.config.ticks_per_slot * 100)

                self.config.external_redis_communicator.approve_aggregator_commands()

                current_tick_in_slot = tick_no % self.config.ticks_per_slot
                if (self.config.external_connection_enabled and
                        global_objects.external_global_stats.is_it_time_for_external_tick(
                            current_tick_in_slot)):
                    global_objects.external_global_stats.update()

                self.area.tick_and_dispatch()
                self.area.execute_actions_after_tick_event()
                bid_offer_matcher.event_tick(
                    current_tick_in_slot=current_tick_in_slot,
                    slot_completion=f"{int((tick_no / self.config.ticks_per_slot) * 100)}%",
                    market_slot=self.progress_info.next_slot_str)
                self.config.external_redis_communicator.\
                    publish_aggregator_commands_responses_events()

                self._time.handle_slowdown_and_realtime(tick_no, self.config, self.status)

                if self.status.stopped:
                    log.error("Received stop command for configuration id %s and job id %s.",
                              gsy_e.constants.CONFIGURATION_ID, self.simulation_id)
                    sleep(5)
                    self._simulation_stopped_finish_actions(slot_count, status="stopped")
                    return

                self._external_events.tick_update(self.area)

            self._results.update_csv_on_market_cycle(slot_no, self.area)
            self.status.handle_incremental_mode()
            self._results.update_and_send_results(simulation=self)

        self._simulation_stopped_finish_actions(slot_count)

    def _simulation_stopped_finish_actions(self, slot_count: int, status="finished") -> None:
        self.status.sim_status = status
        self._deactivate_areas(self.area)
        self.config.external_redis_communicator.publish_aggregator_commands_responses_events()
        bid_offer_matcher.event_finish()
        if not self.status.stopped:
            self.progress_info.update(
                slot_count - 1, slot_count, self._time, self.config)
            paused_duration = duration(seconds=self._time.paused_time)
            self.progress_info.log_simulation_finished(paused_duration, self.config)
        self._results.update_and_send_results(simulation=self)
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

                if self.status.finished and cmd in {"p", "+", "-"}:
                    log.info("Simulation has finished. The commands [p, +, -] are unavailable.")
                    continue

                if cmd == "r":
                    self.reset()
                elif cmd == "i":
                    self._info()
                elif cmd == "p":
                    self.status.toggle_pause()
                    break
                elif cmd == "q":
                    raise KeyboardInterrupt()
                elif cmd == "s":
                    self.status.stop()

            if sleep_period == 0 or time() - start >= sleep_period:
                break

    def _handle_paused(self, console: NonBlockingConsole) -> None:
        if console is not None:
            self._handle_input(console)
            self.status.handle_pause_after(self._time_since_start)
        paused_flag = False
        if self.status.paused:
            if console:
                log.critical("Simulation paused. Press 'p' to resume or resume from API.")
            else:
                self._results.update_and_send_results(simulation=self)
            start = time()
        while self.status.paused:
            paused_flag = True
            if console:
                self._handle_input(console, 0.1)
                self.status.handle_pause_timeout()
            sleep(0.5)

        if console and paused_flag:
            log.critical("Simulation resumed")
            self._time.paused_time += time() - start

    def _info(self) -> None:
        info = self.config.as_dict()
        slot, tick = divmod(self.area.current_tick, self.config.ticks_per_slot)
        percent = self.area.current_tick / self.config.total_ticks * 100
        slot_count = self.config.sim_duration // self.config.slot_length
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
            "paused": self.status.paused,
            "seed": self._setup.seed,
            "sim_status": self.status.sim_status,
            "stopped": self.status.stopped,
            "simulation_id": self.simulation_id,
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
                        "Simulation id: %s", area.uuid, self.simulation_id)
        else:
            area.restore_state(saved_area_state[area.uuid])
        for child in area.children:
            self._restore_area_state(child, saved_area_state)

    def restore_area_state_all_areas(self, saved_area_state: dict) -> None:
        """Restore state of all areas."""
        self._restore_area_state(self.area, saved_area_state)

    def restore_global_state(self, saved_state: dict) -> None:
        """Restore global state of simulation."""
        self.status.paused = saved_state["paused"]
        self._setup.seed = saved_state["seed"]
        self.status.sim_status = saved_state["sim_status"]
        self.status.stopped = saved_state["stopped"]
        self.simulation_id = saved_state["simulation_id"]
        if saved_state["run_start"] != "":
            self._time.start_time = str_to_pendulum_datetime(saved_state["run_start"])
        self._time.paused_time = saved_state["paused_time"]
        self.progress_info.current_slot_number = saved_state["slot_number"]
        self._time.slot_length_realtime = duration(
            seconds=saved_state["slot_length_realtime_s"])

    @staticmethod
    def _compute_memory_info():
        gc.collect()
        process = psutil.Process(os.getpid())
        mbs_used = process.memory_info().rss / 1000000.0
        log.debug("Used %s MBs.", mbs_used)


class CoefficientSimulation(Simulation):
    """Start and control a simulation with coefficient trading."""

    area: "CoefficientArea"
    _results: CoefficientSimulationResultsManager

    def _init(self) -> None:
        # has to be called before load_setup_module():
        global_objects.profiles_handler.activate()

        self.area = self._setup.load_setup_module()

        # has to be called after areas are initiated in order to retrieve the profile uuids
        global_objects.profiles_handler.update_time_and_buffer_profiles(
            GlobalConfig.start_date, area=self.area)

        self._results.init_results(self.simulation_id, self.area, self._setup)
        self._results.update_and_send_results(self)

        log.debug("Starting simulation with config %s", self.config)

        self.area.activate_energy_parameters(self.config.start_date)

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

        self.config.external_redis_communicator. \
            publish_aggregator_commands_responses_events()

    def _cycle_markets(self, slot_no: int) -> None:
        # order matters here;
        # update of ProfilesHandler has to be called before cycle_coefficients_trading
        global_objects.profiles_handler.update_time_and_buffer_profiles(
            self._get_current_market_time_slot(slot_no), area=self.area)

        self.area.cycle_coefficients_trading(self.progress_info.current_slot_time)

    def _execute_simulation(
            self, slot_resume: int, _tick_resume: int, console: NonBlockingConsole = None) -> None:
        slot_count, slot_resume = (
            self._time.calc_resume_slot_and_count_realtime(
                self.config, slot_resume, self.status))

        self.config.external_redis_communicator.activate()

        self._time.reset(not_restored_from_state=(slot_resume == 0))

        for slot_no in range(slot_resume, slot_count):
            self._handle_paused(console)

            self.progress_info.update(slot_no, slot_count, self._time, self.config)

            self._cycle_markets(slot_no)

            self._handle_external_communication()

            scm_manager = SCMManager(self.area, self._get_current_market_time_slot(slot_no))

            self.area.calculate_home_after_meter_data(
                self.progress_info.current_slot_time, scm_manager)

            scm_manager.calculate_community_after_meter_data()
            self.area.trigger_energy_trades(scm_manager)
            scm_manager.accumulate_community_trades()

            if ConstSettings.SCMSettings.MARKET_ALGORITHM == CoefficientAlgorithm.DYNAMIC.value:
                self.area.change_home_coefficient_percentage(scm_manager)

            # important: SCM manager has to be updated before sending the results
            self._results.update_scm_manager(scm_manager)

            self._results.update_and_send_results(self)

            self._external_events.update(self.area)

            # self._compute_memory_info()

            self._time.handle_slowdown_and_realtime_scm(
                slot_no, slot_count, self.config, self.status)

            if self.status.stopped:
                log.error("Received stop command for configuration id %s and job id %s.",
                          gsy_e.constants.CONFIGURATION_ID, self.simulation_id)
                sleep(5)
                self._simulation_stopped_finish_actions(slot_count, status="stopped")
                return

            self._results.update_csv_files(slot_no, self.progress_info.current_slot_time,
                                           self.area, scm_manager)
            self.status.handle_incremental_mode()

        self._simulation_stopped_finish_actions(slot_count)

    def _simulation_stopped_finish_actions(self, slot_count: int, status="finished") -> None:
        self.status.sim_status = status
        self._deactivate_areas(self.area)
        self.config.external_redis_communicator.publish_aggregator_commands_responses_events()
        if not self.status.stopped:
            self.progress_info.update(
                slot_count - 1, slot_count, self._time, self.config)
            paused_duration = duration(seconds=self._time.paused_time)
            self.progress_info.log_simulation_finished(paused_duration, self.config)
        self._results.update_and_send_results(self)

        self._results.save_csv_results(self.area)


def simulation_class_factory():
    """
    Factory method that selects the correct simulation class for market or coefficient trading.
    """
    return (
        CoefficientSimulation
        if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.COEFFICIENTS.value
        else Simulation
    )


def run_simulation(
        setup_module_name: str = "", simulation_config: SimulationConfig = None,
        simulation_events: str = None, redis_job_id: str = None, saved_sim_state: dict = None,
        slot_length_realtime: Duration = None, kwargs: dict = None) -> Dict:
    """Initiate simulation class and start simulation."""
    # pylint: disable=too-many-arguments,protected-access
    try:
        redis_job_id = (
            redis_job_id if not saved_sim_state
            else saved_sim_state["general"]["simulation_id"])
        simulation = simulation_class_factory()(
            setup_module_name=setup_module_name,
            simulation_config=simulation_config,
            simulation_events=simulation_events,
            slot_length_realtime=slot_length_realtime,
            redis_job_id=redis_job_id,
            **kwargs
        )
    except SimulationException as ex:
        log.error(ex)
        return {}

    if (saved_sim_state and
            saved_sim_state["areas"] != {} and
            saved_sim_state["general"]["sim_status"] in ["running", "paused"]):
        simulation.restore_global_state(saved_sim_state["general"])
        simulation.restore_area_state_all_areas(saved_sim_state["areas"])
        simulation.run(initial_slot=saved_sim_state["general"]["slot_number"])
    else:
        simulation.run()

    return simulation._results._endpoint_buffer.simulation_state
