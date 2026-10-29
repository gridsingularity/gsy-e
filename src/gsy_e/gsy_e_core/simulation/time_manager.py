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
import sys
from dataclasses import dataclass
from logging import getLogger
from time import mktime, sleep, time
from typing import TYPE_CHECKING, Tuple

from gsy_framework.constants_limits import TIME_ZONE
from pendulum import DateTime, duration, now

import gsy_e.constants

if TYPE_CHECKING:
    from gsy_e.models.area import Area, AreaBase
    from gsy_e.models.config import SimulationConfig
    from gsy_e.gsy_e_core.simulation.status_manager import SimulationStatusManager

log = getLogger(__name__)


class TimeManagerBase:
    """Base class for the Simulation/Canary Network time managers."""

    @staticmethod
    def _sleep_and_wake_up_if_stopped(
        sleep_time_s: float, status: "SimulationStatusManager"
    ) -> None:
        if sleep_time_s > 0:
            start_time = time()
            while time() - start_time < sleep_time_s and not status.stopped:
                sleep(5)

    @staticmethod
    def _sleep_no_realtime(sleep_time_s: float):
        if sleep_time_s > 0:
            sleep(sleep_time_s)


@dataclass
class SimulationTimeManager(TimeManagerBase):
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
        self,
        config: "SimulationConfig",
        slot_resume: int,
        tick_resume: int,
        area: "AreaBase",
        status: "SimulationStatusManager",
    ) -> Tuple[int, int, int]:
        # pylint: disable = too-many-arguments
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

            self._sleep_and_wake_up_if_stopped(seconds_until_next_tick, status)

        if self.slot_length_realtime:
            self.tick_length_realtime_s = self.slot_length_realtime.seconds / config.ticks_per_slot
        return slot_count, slot_resume, tick_resume

    def handle_slowdown_and_realtime(
        self, tick_no: int, config: "SimulationConfig", status: "SimulationStatusManager"
    ) -> None:
        """
        Handle simulation slowdown and simulation realtime mode, and sleep the simulation
        accordingly.
        """
        if gsy_e.constants.RUN_IN_REALTIME:
            tick_runtime_s = time() - self.tick_time_counter
            sleep_time_s = config.tick_length.seconds - tick_runtime_s
            self._sleep_and_wake_up_if_stopped(sleep_time_s, status)
        elif self.slot_length_realtime:
            current_expected_tick_time = self.tick_time_counter + self.tick_length_realtime_s
            sleep_time_s = current_expected_tick_time - now(tz=TIME_ZONE).timestamp()
            self._sleep_no_realtime(sleep_time_s)
        else:
            return

        if sleep_time_s > 0:
            log.debug(
                "Tick %s/%s: Sleep time of %s s was applied",
                tick_no + 1,
                config.ticks_per_slot,
                sleep_time_s,
            )

        self.tick_time_counter = time()
