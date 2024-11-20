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

import sys
from dataclasses import dataclass
from logging import getLogger
from time import time
from typing import TYPE_CHECKING, Tuple

import pendulum
from pendulum import DateTime, duration, now

import gsy_e.constants
from gsy_e.constants import TIME_ZONE
from gsy_e.gsy_e_core.simulation.time_manager import TimeManagerBase

if TYPE_CHECKING:
    from gsy_e.models.config import SimulationConfig
    from gsy_e.gsy_e_core.simulation.status_manager import SimulationStatusManager

log = getLogger(__name__)


@dataclass
class SimulationTimeManagerScm(TimeManagerBase):
    """Handles simulation time management."""

    start_time: DateTime = None
    paused_time: int = 0  # Time spent in paused state, in seconds
    slot_length_realtime: duration = None
    hours_of_delay: int = 0
    slot_time_counter: float = time()

    def __post_init__(self):
        self.start_time: DateTime = self._set_start_time()

    def _set_start_time(self):
        # Set SCM start time. By default it is 2 days before the current datetime.
        return now(tz=TIME_ZONE) - duration(hours=self.hours_of_delay)

    def reset(self, not_restored_from_state: bool = True) -> None:
        """
        Restore time-related parameters of the simulation to their default values.
        Mainly useful when resetting the simulation.
        """
        self.slot_time_counter = int(time())
        if not_restored_from_state:
            self.start_time = self._set_start_time()
            self.paused_time = 0

    def handle_slowdown_and_realtime_scm(
        self,
        slot_no: int,
        slot_count: int,
        config: "SimulationConfig",
        status: "SimulationStatusManager",
    ) -> None:
        """
        Handle simulation slowdown and simulation realtime mode, and sleep the simulation
        accordingly for SCM simulations.
        """
        slot_length_realtime_s = (
            self.slot_length_realtime.total_seconds() if self.slot_length_realtime else None
        )

        if gsy_e.constants.RUN_IN_REALTIME:
            slot_runtime_s = time() - self.slot_time_counter
            sleep_time_s = config.slot_length.total_seconds() - slot_runtime_s
            self._sleep_and_wake_up_if_stopped(sleep_time_s, status)
        elif slot_length_realtime_s:
            current_expected_slot_time = self.slot_time_counter + slot_length_realtime_s
            sleep_time_s = current_expected_slot_time - now(tz=TIME_ZONE).timestamp()
            self._sleep_no_realtime(sleep_time_s)
        else:
            return

        if sleep_time_s > 0:
            log.debug(
                "Slot %s/%s: Sleep time of %s s was applied", slot_no, slot_count, sleep_time_s
            )

        self.slot_time_counter = int(time())

    @staticmethod
    def get_start_time_on_init(config: "SimulationConfig") -> DateTime:
        """Return the start tim of the simulation."""
        if gsy_e.constants.RUN_IN_REALTIME:
            today = pendulum.today(tz=TIME_ZONE)
            seconds_since_midnight = time() - today.int_timestamp
            slot_no = int(seconds_since_midnight // config.slot_length.seconds) + 1
            start_time = config.start_date + duration(seconds=slot_no * config.slot_length.seconds)
        else:
            start_time = config.start_date
        return start_time

    def calc_resume_slot_and_count_realtime(
        self, config: "SimulationConfig", slot_resume: int, status: "SimulationStatusManager"
    ) -> Tuple[int, int]:
        """Calculate total slot count and the slot where to resume the realtime simulation."""
        slot_count = int(config.sim_duration / config.slot_length)

        if gsy_e.constants.RUN_IN_REALTIME:
            slot_count = sys.maxsize

            today = pendulum.today(tz=TIME_ZONE)
            seconds_since_midnight = time() - today.int_timestamp
            slot_resume = int(seconds_since_midnight // config.slot_length.seconds) + 1
            seconds_elapsed_in_slot = seconds_since_midnight % config.slot_length.seconds
            sleep_time_s = config.slot_length.total_seconds() - seconds_elapsed_in_slot
            self._sleep_and_wake_up_if_stopped(sleep_time_s, status)
            log.debug(
                "Resume Slot %s/%s: Sleep time of %s s was applied",
                slot_resume,
                slot_count,
                sleep_time_s,
            )

        return slot_count, slot_resume
