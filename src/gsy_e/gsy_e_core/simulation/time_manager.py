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

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import SpotMarketTypeEnum
from pendulum import DateTime, duration, now

import gsy_e.constants
from gsy_e.constants import TIME_ZONE

if TYPE_CHECKING:
    from gsy_e.models.area import Area, AreaBase
    from gsy_e.models.config import SimulationConfig

log = getLogger(__name__)


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
            self, config: "SimulationConfig", slot_resume: int, tick_resume: int, area: "AreaBase"
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

    def handle_slowdown_and_realtime(self, tick_no: int, config: "SimulationConfig") -> None:
        """
        Handle simulation slowdown and simulation realtime mode, and sleep the simulation
        accordingly.
        """
        if gsy_e.constants.RUN_IN_REALTIME:
            tick_runtime_s = time() - self.tick_time_counter
            sleep_time_s = config.tick_length.seconds - tick_runtime_s
        elif self.slot_length_realtime:
            current_expected_tick_time = self.tick_time_counter + self.tick_length_realtime_s
            sleep_time_s = current_expected_tick_time - now().timestamp()
        else:
            return

        if sleep_time_s > 0:
            sleep(sleep_time_s)
            log.debug("Tick %s/%s: Sleep time of %s s was applied",
                      tick_no + 1, config.ticks_per_slot, sleep_time_s)

        self.tick_time_counter = time()


@dataclass
class SimulationTimeManagerScm:
    """Handles simulation time management."""
    start_time: DateTime = now(tz=TIME_ZONE)
    paused_time: int = 0  # Time spent in paused state, in seconds
    slot_length_realtime: duration = None
    slot_time_counter: float = time()

    def reset(self, not_restored_from_state: bool = True) -> None:
        """
        Restore time-related parameters of the simulation to their default values.
        Mainly useful when resetting the simulation.
        """
        self.slot_time_counter = time()
        if not_restored_from_state:
            self.start_time = now(tz=TIME_ZONE)
            self.paused_time = 0

    def handle_slowdown_and_realtime_scm(self, slot_no: int, slot_count: int,
                                         config: "SimulationConfig") -> None:
        """
        Handle simulation slowdown and simulation realtime mode, and sleep the simulation
        accordingly for SCM simulations.
        """

        slot_length_realtime_s = self.slot_length_realtime.total_seconds()

        if gsy_e.constants.RUN_IN_REALTIME:
            slot_runtime_s = time() - self.slot_time_counter
            sleep_time_s = config.slot_length.total_seconds() - slot_runtime_s
        elif slot_length_realtime_s:
            current_expected_tick_time = self.slot_time_counter + slot_length_realtime_s
            sleep_time_s = current_expected_tick_time - now().timestamp()
        else:
            return

        if sleep_time_s > 0:
            sleep(sleep_time_s)
            log.debug("Slot %s/%s: Sleep time of %s s was applied",
                      slot_no, slot_count, sleep_time_s)

        self.slot_time_counter = time()

    @staticmethod
    def calc_resume_slot_and_count_realtime(
            config: "SimulationConfig", slot_resume: int) -> Tuple[int, int]:
        """Calculate total slot count and the slot where to resume the realtime simulation."""
        slot_count = int(config.sim_duration / config.slot_length)

        if gsy_e.constants.RUN_IN_REALTIME:
            slot_count = sys.maxsize

            today = datetime.date.today()
            seconds_since_midnight = time() - mktime(today.timetuple())
            slot_resume = int(seconds_since_midnight // config.slot_length.seconds) + 1
            seconds_elapsed_in_slot = seconds_since_midnight % config.slot_length.seconds
            sleep_time_s = config.slot_length.total_seconds() - seconds_elapsed_in_slot
            sleep(sleep_time_s)

        return slot_count, slot_resume


def simulation_time_manager_factory(slot_length_realtime: duration):
    """Factory for time manager objects."""
    if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.COEFFICIENTS.value:
        return SimulationTimeManagerScm(slot_length_realtime=slot_length_realtime)
    return SimulationTimeManager(slot_length_realtime=slot_length_realtime)
