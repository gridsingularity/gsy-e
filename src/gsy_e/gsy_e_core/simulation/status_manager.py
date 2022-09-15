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

from dataclasses import dataclass
from logging import getLogger
from time import time

from pendulum import Duration, duration

from gsy_e.constants import SIMULATION_PAUSE_TIMEOUT

log = getLogger(__name__)


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
