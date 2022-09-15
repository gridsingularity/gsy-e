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
from gsy_e.models.config import SimulationConfig

if TYPE_CHECKING:
    from gsy_e.models.area import Area, AreaBase
    from gsy_e.gsy_e_core.simulation_utils.simulation_status_manager import SimulationStatusManager
    from gsy_e.gsy_e_core.simulation_utils.simulation_progress_info import SimulationProgressInfo

log = getLogger(__name__)


class SimulationExternalEvents:
    """
    Handle signals that affect the simulation state, that arrive from Redis. Consists of live
    events and signals that change the simulation status.
    """
    def __init__(self, simulation_id: str, config: SimulationConfig,
                 state_params: "SimulationStatusManager", progress_info: "SimulationProgressInfo",
                 area: "Area") -> None:
        # pylint: disable=too-many-arguments
        self.live_events = LiveEvents(config)
        self.redis_connection = RedisSimulationCommunication(
            state_params, simulation_id, self.live_events, progress_info, area)

    def update(self, area: "AreaBase") -> None:
        """
        Update the simulation according to any live events received. Triggered every market slot.
        """
        self.live_events.handle_all_events(area)
