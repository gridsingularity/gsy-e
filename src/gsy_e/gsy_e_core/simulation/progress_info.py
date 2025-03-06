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
from typing import TYPE_CHECKING

from pendulum import DateTime, Duration, duration, now
from gsy_framework.utils import format_datetime
from gsy_framework.constants_limits import TIME_ZONE, GlobalConfig


if TYPE_CHECKING:
    from gsy_e.gsy_e_core.simulation.time_manager import SimulationTimeManager
    from gsy_e.models.config import SimulationConfig

log = getLogger(__name__)


class SimulationProgressInfo:
    """Information about the simulation progress."""

    def __init__(self):
        self.eta = duration(seconds=0)  # Estimated Time of Arrival (end of the simulation)
        self.elapsed_time = duration(seconds=0)  # Time passed since the start of the simulation
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
        return config.start_date.add(minutes=config.slot_length.total_minutes() * slot_number)

    def update(
        self,
        slot_no: int,
        slot_count: int,
        time_params: "SimulationTimeManager",
        config: "SimulationConfig",
    ) -> None:
        """Update progress info according to the simulation progress."""
        run_duration = (
            now(tz=TIME_ZONE) - time_params.start_time - duration(seconds=time_params.paused_time)
        )

        if GlobalConfig.RUN_IN_REALTIME:
            self.eta = None
            self.percentage_completed = 0.0
        else:
            self.eta = (run_duration / (slot_no + 1) * slot_count) - run_duration
            self.percentage_completed = (slot_no + 1) / slot_count * 100

        self.elapsed_time = run_duration
        self.current_slot_str = self._get_market_slot_time_str(slot_no, config)
        self.current_slot_time = self._get_market_slot_time(slot_no, config)
        self.next_slot_str = self._get_market_slot_time_str(slot_no + 1, config)
        self.current_slot_number = slot_no

        log.warning(
            "Slot %s of %s - (%.1f %%) %s elapsed, ETA: %s",
            slot_no + 1,
            slot_count,
            self.percentage_completed,
            self.elapsed_time,
            self.eta,
        )

    def log_simulation_finished(
        self, paused_duration: Duration, config: "SimulationConfig"
    ) -> None:
        """Log that the simulation has finished."""
        log.info(
            "Run finished in %s%s / %.2fx real time",
            self.elapsed_time,
            f" ({paused_duration} paused)" if paused_duration else "",
            config.sim_duration / (self.elapsed_time - paused_duration),
        )
