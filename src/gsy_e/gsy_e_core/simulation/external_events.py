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

from gsy_e.gsy_e_core.live_events import LiveEvents
from gsy_e.gsy_e_core.redis_connections.simulation import RedisSimulationCommunication

if TYPE_CHECKING:
    from gsy_e.models.area import AreaBase
    from gsy_e.gsy_e_core.simulation import Simulation

log = getLogger(__name__)


class SimulationExternalEvents:
    """
    Handle signals that affect the simulation state, that arrive from Redis.

    Consists of live events and signals that change the simulation status.
    """
    def __init__(self, simulation: "Simulation") -> None:
        self.live_events = LiveEvents(simulation.config)
        self.redis_connection = RedisSimulationCommunication(
            simulation_status=simulation.status,
            simulation_id=simulation.simulation_id,
            live_events=self.live_events,
            progress_info=simulation.progress_info,
            area=simulation.area)

    def update(self, area: "AreaBase") -> None:
        """
        Update the simulation according to any live events received. Triggered every market slot.
        """
        self.live_events.handle_all_events(area)

    def tick_update(self, area: "AreaBase") -> None:
        """
        Update the simulation according to any live events received. Triggered every tick.
        """
        self.live_events.handle_tick_events(area)
