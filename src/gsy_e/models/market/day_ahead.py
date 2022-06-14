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
from typing import TYPE_CHECKING

from gsy_framework.constants_limits import GlobalConfig
from pendulum import DateTime, duration

from gsy_e.models.market.future import FutureMarkets

if TYPE_CHECKING:
    from gsy_e.models.config import SimulationConfig

DAY_AHEAD_MARKET_LENGTH_MINUTES = 60
DAY_AHEAD_HOUR_OF_ROTATION = 13


class DayAheadMarkets(FutureMarkets):
    """Day-ahead market class"""

    def create_future_markets(self, current_market_time_slot: DateTime,
                              config: "SimulationConfig") -> None:
        if not GlobalConfig.DAY_AHEAD_DURATION_DAYS:
            return
        start_time = current_market_time_slot.set(hour=0, minute=0).add(days=1)
        # add one day minus one time_slot
        end_time = start_time.add(days=GlobalConfig.DAY_AHEAD_DURATION_DAYS,
                                  minutes=-DAY_AHEAD_MARKET_LENGTH_MINUTES)
        self._create_future_markets(duration(minutes=DAY_AHEAD_MARKET_LENGTH_MINUTES),
                                    start_time, end_time, config)
