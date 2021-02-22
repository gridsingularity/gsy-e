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

import click
import platform
import os
import psutil
import gc
import sys
import datetime

from pendulum import now, duration
from ptpython.repl import embed
from time import sleep, time, mktime
from numpy import random
from importlib import import_module
from logging import getLogger

from d3a.constants import TIME_ZONE, DATE_TIME_FORMAT, SIMULATION_PAUSE_TIMEOUT
from d3a.d3a_core.exceptions import SimulationException
from d3a.d3a_core.export import ExportAndPlot
from d3a.models.config import SimulationConfig
from d3a.models.power_flow.pandapower import PandaPowerFlow
# noinspection PyUnresolvedReferences
from d3a import setup as d3a_setup  # noqa
from d3a.d3a_core.util import NonBlockingConsole, validate_const_settings_for_simulation, \
    get_market_slot_time_str
from d3a.d3a_core.sim_results.endpoint_buffer import SimulationEndpointBuffer
from d3a.d3a_core.redis_connections.redis_communication import RedisSimulationCommunication
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from d3a_interface.exceptions import D3AException
from d3a_interface.utils import format_datetime, str_to_pendulum_datetime
from d3a.models.area.event_deserializer import deserialize_events_to_areas
from d3a.d3a_core.live_events import LiveEvents
from d3a.d3a_core.sim_results.file_export_endpoints import FileExportEndpoints
from d3a.d3a_core.global_objects import GlobalObjects
from d3a.blockchain.constants import ENABLE_SUBSTRATE
import d3a.constants


if platform.python_implementation() != "PyPy" and \
        ENABLE_SUBSTRATE:
    from d3a.blockchain import BlockChainInterface

log = getLogger(__name__)


RANDOM_SEED_MAX_VALUE = 1000000


class SimulationResetException(Exception):
    pass


class SimulationProgressInfo:
    def __init__(self):
        self.eta = duration(seconds=0)
        self.elapsed_time = duration(seconds=0)
        self.percentage_completed = 0
        self.next_slot_str = ""
        self.current_slot_str = ""
        self.current_slot_number = 0


class Simulation:
    def __init__(self, setup_module_name: str, simulation_config: SimulationConfig = None,
                 simulation_events: str = None, seed=None,
                 paused: bool = False, pause_after: duration = None, repl: bool = False,
                 no_export: bool = False, export_path: str = None,
                 export_subdir: str = None, redis_job_id=None, enable_bc=False,
                 slot_length_realtime=None):
        self.initial_params = dict(
            slot_length_realtime=slot_length_realtime,
            seed=seed,
            paused=paused,
            pause_after=pause_after
        )
        self.progress_info = SimulationProgressInfo()
        self.simulation_config = simulation_config
        self.global_objects = GlobalObjects()
        self.use_repl = repl
        self.export_on_finish = not no_export
        self.export_path = export_path

        self.sim_status = "initializing"
        self.is_timed_out = False

        if export_subdir is None:
            self.export_subdir = \
                now(tz=TIME_ZONE).format(f"{DATE_TIME_FORMAT}:ss")
        else:
            self.export_subdir = export_subdir

        self.setup_module_name = setup_module_name
        self.use_bc = enable_bc
        self.is_stopped = False

        self.live_events = LiveEvents(self.simulation_config)
        self.redis_connection = RedisSimulationCommunication(self, redis_job_id, self.live_events)
        self._simulation_id = redis_job_id
        self._started_from_cli = redis_job_id is None

        self.run_start = None
        self.paused_time = None

        self._load_setup_module()
        self._init(**self.initial_params, redis_job_id=redis_job_id)

        deserialize_events_to_areas(simulation_events, self.area)

        validate_const_settings_for_simulation()

    def _set_traversal_length(self):
        no_of_levels = self._get_setup_levels(self.area) + 1
        num_ticks_to_propagate = no_of_levels * 2
        ConstSettings.GeneralSettings.MAX_OFFER_TRAVERSAL_LENGTH = 2
        time_to_propagate_minutes = num_ticks_to_propagate * \
            self.simulation_config.tick_length.seconds / 60.
        log.info("Setup has {} levels, offers/bids need at least {} minutes "
                 "({} ticks) to propagate.".format(no_of_levels, time_to_propagate_minutes,
                                                   ConstSettings.GeneralSettings.
                                                   MAX_OFFER_TRAVERSAL_LENGTH,))

    def _get_setup_levels(self, area, level_count=0):
        level_count += 1
        count_list = [self._get_setup_levels(child, level_count)
                      for child in area.children if child.children]
        return max(count_list) if len(count_list) > 0 else level_count

    def _load_setup_module(self):
        try:
            if ConstSettings.GeneralSettings.SETUP_FILE_PATH is None:
                self.setup_module = import_module(".{}".format(self.setup_module_name),
                                                  'd3a.setup')
            else:
                sys.path.append(ConstSettings.GeneralSettings.SETUP_FILE_PATH)
                self.setup_module = import_module("{}".format(self.setup_module_name))
            log.debug("Using setup module '%s'", self.setup_module_name)
        except ImportError as ex:
            raise SimulationException(
                "Invalid setup module '{}'".format(self.setup_module_name)) from ex

    def _init(self, slot_length_realtime, seed, paused, pause_after, redis_job_id):
        self.paused = paused
        self.pause_after = pause_after
        self.slot_length_realtime = slot_length_realtime

        if seed is not None:
            random.seed(int(seed))
        else:
            random_seed = random.randint(0, RANDOM_SEED_MAX_VALUE)
            random.seed(random_seed)
            self.initial_params["seed"] = random_seed
            log.info("Random seed: {}".format(random_seed))

        self.area = self.setup_module.get_setup(self.simulation_config)
        self.area._global_objects = self.global_objects
        self.endpoint_buffer = SimulationEndpointBuffer(
            redis_job_id, self.initial_params,
            self.area, self.should_export_results)
        if self.should_export_results:
            self.file_stats_endpoint = FileExportEndpoints()

        if self.export_on_finish and self.should_export_results:
            self.export = ExportAndPlot(self.area, self.export_path, self.export_subdir,
                                        self.file_stats_endpoint, self.endpoint_buffer)
        self._update_and_send_results()

        if GlobalConfig.POWER_FLOW:
            self.power_flow = PandaPowerFlow(self.area)
            self.power_flow.run_power_flow()
        self.bc = None
        if self.use_bc:
            self.bc = BlockChainInterface()
        log.debug("Starting simulation with config %s", self.simulation_config)

        self._set_traversal_length()

        self.area.activate(self.bc)

    @property
    def finished(self):
        return self.area.current_tick >= self.area.config.total_ticks

    @property
    def time_since_start(self):
        return self.area.current_tick * self.simulation_config.tick_length

    def reset(self):
        """
        Reset simulation to initial values and restart the run.
        """
        log.info("=" * 15 + " Simulation reset requested " + "=" * 15)
        self._init(**self.initial_params)
        self.run()
        raise SimulationResetException

    def stop(self):
        self.is_stopped = True

    def deactivate_areas(self, area):
        """
        For putting the last market into area.past_markets
        """
        area.deactivate()
        for child in area.children:
            self.deactivate_areas(child)

    def run(self, initial_slot=0):
        self.sim_status = "running"
        self.is_stopped = False
        while True:
            if initial_slot == 0:
                self.run_start = now(tz=TIME_ZONE)
                self.paused_time = 0

            tick_resume = 0
            try:
                self._run_cli_execute_cycle(initial_slot, tick_resume) \
                    if self._started_from_cli \
                    else self._execute_simulation(initial_slot, tick_resume)
            except KeyboardInterrupt:
                break
            except SimulationResetException:
                break
            else:
                break

    def _run_cli_execute_cycle(self, slot_resume, tick_resume):
        with NonBlockingConsole() as console:
            self._execute_simulation(slot_resume, tick_resume, console)

    def update_area_stats(self, area, endpoint_buffer):
        for child in area.children:
            self.update_area_stats(child, endpoint_buffer)
        bills = endpoint_buffer.results_handler.all_ui_results["bills"].get(area.uuid, {})
        area.stats.update_aggregated_stats({"bills": bills})
        area.stats.kpi.update(
            endpoint_buffer.results_handler.all_ui_results["kpi"].get(area.uuid, {}))

    def _update_and_send_results(self, is_final=False):
        self.endpoint_buffer.update_stats(
            self.area, self.status, self.progress_info, self.current_state)
        self.update_area_stats(self.area, self.endpoint_buffer)
        if self.export_on_finish and self.should_export_results and \
                self.area.current_market is not None and d3a.constants.D3A_TEST_RUN:
            self.export.raw_data_to_json(
                self.area.current_market.time_slot_str,
                self.endpoint_buffer.flattened_area_core_stats_dict
            )
        if self.should_export_results:
            self.file_stats_endpoint(self.area)
            return
        if is_final or self.is_stopped:
            self.redis_connection.publish_results(self.endpoint_buffer)
        else:
            self.redis_connection.publish_intermediate_results(
                self.endpoint_buffer
            )

    def _update_progress_info(self, slot_no, slot_count):
        run_duration = (
                now(tz=TIME_ZONE) - self.run_start -
                duration(seconds=self.paused_time)
        )

        if d3a.constants.RUN_IN_REALTIME:
            self.progress_info.eta = None
            self.progress_info.percentage_completed = 0.0
        else:
            self.progress_info.eta = (run_duration / (slot_no + 1) * slot_count) - run_duration
            self.progress_info.percentage_completed = (slot_no + 1) / slot_count * 100

        self.progress_info.elapsed_time = run_duration
        self.progress_info.current_slot_str = get_market_slot_time_str(
            slot_no, self.simulation_config)
        self.progress_info.next_slot_str = get_market_slot_time_str(
            slot_no + 1, self.simulation_config)
        self.progress_info.current_slot_number = slot_no

    def set_area_current_tick(self, area, current_tick):
        area.current_tick = current_tick
        for child in area.children:
            self.set_area_current_tick(child, current_tick)

    def _execute_simulation(self, slot_resume, tick_resume, console=None):
        self.current_expected_tick_time = self.run_start
        config = self.simulation_config
        slot_count = int(config.sim_duration / config.slot_length)

        config.external_redis_communicator.sub_to_aggregator()
        config.external_redis_communicator.start_communication()

        if d3a.constants.RUN_IN_REALTIME:
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
            self.set_area_current_tick(self.area, ticks_since_midnight)

            sleep(seconds_until_next_tick)

        if self.slot_length_realtime:
            self.tick_length_realtime_s = self.slot_length_realtime.seconds / \
                                          self.simulation_config.ticks_per_slot

        for slot_no in range(slot_resume, slot_count):
            self._update_progress_info(slot_no, slot_count)

            log.warning(f"Slot {slot_no + 1} of {slot_count} - "
                        f"({self.progress_info.percentage_completed:.1f}%) "
                        f"{self.progress_info.elapsed_time} elapsed, "
                        f"ETA: {self.progress_info.eta}")

            self.global_objects.update(self.area)

            self.area.cycle_markets()
            self._update_and_send_results()
            self.live_events.handle_all_events(self.area)

            gc.collect()
            process = psutil.Process(os.getpid())
            mbs_used = process.memory_info().rss / 1000000.0
            log.debug(f"Used {mbs_used} MBs.")

            self.tick_time_counter = time()

            for tick_no in range(tick_resume, config.ticks_per_slot):
                self._handle_paused(console)

                # reset tick_resume after possible resume
                tick_resume = 0
                log.trace(f"Tick {tick_no + 1} of {config.ticks_per_slot} in slot "
                          f"{slot_no + 1} ({(tick_no + 1) / config.ticks_per_slot * 100:.1f}%)")

                self.simulation_config.external_redis_communicator.\
                    approve_aggregator_commands()

                self.area.tick_and_dispatch()
                self.area.update_area_current_tick()

                self.simulation_config.external_redis_communicator.\
                    publish_aggregator_commands_responses_events()

                self.handle_slowdown_and_realtime(tick_no)
                self.tick_time_counter = time()

            if self.export_on_finish and self.should_export_results:
                self.export.data_to_csv(self.area, True if slot_no == 0 else False)

            if self.is_stopped:
                log.info("Received stop command.")
                sleep(5)
                break

        self.sim_status = "finished"
        self.deactivate_areas(self.area)
        self.simulation_config.external_redis_communicator.\
            publish_aggregator_commands_responses_events()

        if not self.is_stopped:
            self._update_progress_info(slot_count - 1, slot_count)
            paused_duration = duration(seconds=self.paused_time)
            log.info(
                "Run finished in %s%s / %.2fx real time",
                self.progress_info.elapsed_time,
                " ({} paused)".format(paused_duration) if paused_duration else "",
                config.sim_duration / (self.progress_info.elapsed_time - paused_duration)
            )
        self._update_and_send_results(is_final=True)
        if self.export_on_finish and self.should_export_results:
            log.info("Exporting simulation data.")
            self.export.data_to_csv(self.area, False)
            self.export.area_tree_summary_to_json(self.endpoint_buffer.area_result_dict)
            if GlobalConfig.POWER_FLOW:
                self.export.export(export_plots=self.should_export_results,
                                   power_flow=self.power_flow)
            else:
                self.export.export(self.should_export_results)

        if self.use_repl:
            self._start_repl()

    @property
    def should_export_results(self):
        return not self.redis_connection.is_enabled()

    def handle_slowdown_and_realtime(self, tick_no):
        if d3a.constants.RUN_IN_REALTIME:
            tick_runtime_s = time() - self.tick_time_counter
            sleep(abs(self.simulation_config.tick_length.seconds - tick_runtime_s))
        elif self.slot_length_realtime:
            self.current_expected_tick_time = \
                self.current_expected_tick_time.add(seconds=self.tick_length_realtime_s)
            sleep_time_s = self.current_expected_tick_time.timestamp() - now().timestamp()
            if sleep_time_s > 0:
                sleep(sleep_time_s)
                log.debug(f"Tick {tick_no + 1}/{self.simulation_config.ticks_per_slot}: "
                          f"Sleep time of {sleep_time_s}s was applied")

    def toggle_pause(self):
        if self.finished:
            return False
        self.paused = not self.paused
        return True

    def _handle_input(self, console, sleep: float = 0):
        timeout = 0
        start = 0
        if sleep > 0:
            timeout = sleep / 100
            start = time()
        while True:
            cmd = console.get_char(timeout)
            if cmd:
                if cmd not in {'i', 'p', 'q', 'r', 'R', 's', '+', '-'}:
                    log.critical("Invalid command. Valid commands:\n"
                                 "  [i] info\n"
                                 "  [p] pause\n"
                                 "  [q] quit\n"
                                 "  [r] reset\n"
                                 "  [s] stop\n"
                                 "  [R] start REPL\n")
                    continue

                if self.finished and cmd in {'p', '+', '-'}:
                    log.info("Simulation has finished. The commands [p, +, -] are unavailable.")
                    continue

                if cmd == 'r':
                    self.reset()
                elif cmd == 'R':
                    self._start_repl()
                elif cmd == 'i':
                    self._info()
                elif cmd == 'p':
                    self.paused = not self.paused
                    break
                elif cmd == 'q':
                    raise KeyboardInterrupt()
                elif cmd == 's':
                    self.stop()

            if sleep == 0 or time() - start >= sleep:
                break

    def _handle_paused(self, console):
        if console is not None:
            self._handle_input(console)
            if self.pause_after and self.time_since_start >= self.pause_after:
                self.paused = True
                self.pause_after = None

        paused_flag = False
        if self.paused:
            if console:
                log.critical("Simulation paused. Press 'p' to resume or resume from API.")
            else:
                self._update_and_send_results()
            start = time()
        while self.paused:
            paused_flag = True
            if console:
                self._handle_input(console, 0.1)
            if time() - self.tick_time_counter > SIMULATION_PAUSE_TIMEOUT:
                self.is_timed_out = True
                self.is_stopped = True
                self.paused = False
            if self.is_stopped:
                self.paused = False
            sleep(0.5)

        if console and paused_flag:
            log.critical("Simulation resumed")
            self.paused_time += time() - start

    def _info(self):
        info = self.simulation_config.as_dict()
        slot, tick = divmod(self.area.current_tick, self.simulation_config.ticks_per_slot)
        percent = self.area.current_tick / self.simulation_config.total_ticks * 100
        slot_count = self.simulation_config.sim_duration // self.simulation_config.slot_length
        info.update(slot=slot + 1, tick=tick + 1, slot_count=slot_count, percent=percent)
        log.critical(
            "\n"
            "Simulation configuration:\n"
            "  Duration: %(sim_duration)s\n"
            "  Slot length: %(slot_length)s\n"
            "  Tick length: %(tick_length)s\n"
            "  Market count: %(market_count)d\n"
            "  Ticks per slot: %(ticks_per_slot)d\n"
            "Status:\n"
            "  Slot: %(slot)d / %(slot_count)d\n"
            "  Tick: %(tick)d / %(ticks_per_slot)d\n"
            "  Completed: %(percent).1f%%",
            info
        )

    def _start_repl(self):
        log.debug(
            "An interactive REPL has been started. The root Area is available as "
            "`root_area`.")
        log.debug("Ctrl-D to quit.")
        embed({'root_area': self.area})

    @property
    def status(self):
        if self.is_timed_out:
            return "timed-out"
        elif self.is_stopped:
            return "stopped"
        elif self.paused:
            return "paused"
        else:
            return self.sim_status

    @property
    def current_state(self):
        return {
            "paused": self.paused,
            "seed": self.initial_params["seed"],
            "sim_status": self.sim_status,
            "stopped": self.is_stopped,
            "simulation_id": self._simulation_id,
            "run_start": format_datetime(self.run_start)
            if self.run_start is not None else "",
            "paused_time": self.paused_time,
            "slot_number": self.progress_info.current_slot_number,
            "slot_length_realtime_s": str(self.slot_length_realtime.seconds)
            if self.slot_length_realtime else 0
        }

    def _restore_area_state(self, area, saved_area_state):
        if area.uuid not in saved_area_state:
            log.warning(f"Area {area.uuid} is not part of the saved state. State not restored. "
                        f"Simulation id: {self._simulation_id}")
        else:
            area.restore_state(saved_area_state[area.uuid])
        for child in area.children:
            self._restore_area_state(child, saved_area_state)

    def restore_area_state(self, saved_area_state):
        self._restore_area_state(self.area, saved_area_state)

    def restore_global_state(self, saved_state):
        self.paused = saved_state["paused"]
        self.initial_params["seed"] = saved_state["seed"]
        self.sim_status = saved_state["sim_status"]
        self.is_stopped = saved_state["stopped"]
        self._simulation_id = saved_state["simulation_id"]
        if saved_state["run_start"] != "":
            self.run_start = str_to_pendulum_datetime(saved_state["run_start"])
        self.paused_time = saved_state["paused_time"]
        self.progress_info.current_slot_number = saved_state["slot_number"]
        self.slot_length_realtime = duration(seconds=saved_state["slot_length_realtime_s"])


def run_simulation(setup_module_name="", simulation_config=None, simulation_events=None,
                   redis_job_id=None, saved_sim_state=None,
                   slot_length_realtime=None, kwargs=None):
    try:
        if "pricing_scheme" in kwargs:
            ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME = \
                kwargs.pop("pricing_scheme")

        if saved_sim_state is None:
            simulation = Simulation(
                setup_module_name=setup_module_name,
                simulation_config=simulation_config,
                simulation_events=simulation_events,
                slot_length_realtime=slot_length_realtime,
                redis_job_id=redis_job_id,
                **kwargs
            )
        else:
            simulation = Simulation(
                setup_module_name=setup_module_name,
                simulation_config=simulation_config,
                simulation_events=simulation_events,
                slot_length_realtime=slot_length_realtime,
                redis_job_id=saved_sim_state["general"]["simulation_id"],
                **kwargs
            )

    except D3AException as ex:
        raise click.BadOptionUsage(ex.args[0])

    if saved_sim_state is not None and \
            saved_sim_state["areas"] != {} and \
            saved_sim_state["general"]["sim_status"] in ["running", "paused"]:
        simulation.restore_global_state(saved_sim_state["general"])
        simulation.restore_area_state(saved_sim_state["areas"])
        simulation.run(initial_slot=saved_sim_state["general"]["slot_number"])
    else:
        simulation.run()
