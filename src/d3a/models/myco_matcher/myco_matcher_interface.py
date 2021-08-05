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
from abc import ABC
from typing import Dict


class MycoMatcherInterface(ABC):
    """Interface for myco matchers' public methods."""
    def __init__(self):
        self.area_uuid_markets_mapping: Dict[str, Dict] = {}

    def activate(self):
        """Method to be called upon the activation of MycoMatcher."""

    def update_area_uuid_markets_mapping(self, area_uuid_markets_mapping: Dict[str, Dict]) -> None:
        """Interface for updating the area_uuid_markets_mapping of Myco matchers."""
        self.area_uuid_markets_mapping.update(area_uuid_markets_mapping)

    def match_recommendations(self, **kwargs) -> None:
        """Match bids/offers recommendations."""

    def event_tick(self, **kwargs) -> None:
        """Handler for the tick event."""

    def event_market_cycle(self, **kwargs) -> None:
        """Handler for the market_cycle event."""

    def event_finish(self, **kwargs) -> None:
        """Handler for the finish event."""
