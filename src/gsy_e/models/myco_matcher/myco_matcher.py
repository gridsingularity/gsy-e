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
from typing import Optional, Dict

from gsy_e.gsy_e_core.util import is_external_matching_enabled
from gsy_e.models.myco_matcher import MycoExternalMatcher, MycoInternalMatcher
from gsy_e.models.myco_matcher.myco_matcher_interface import MycoMatcherInterface


class MycoMatcher:
    """
    Myco markets matcher, set the global matcher (Internal/External) and serve as a bridge to it.
    """

    def __init__(self):
        super().__init__()
        self.matcher: Optional[MycoMatcherInterface] = None

    def activate(self):
        """Method to be called upon the activation of MycoMatcher."""
        self.matcher = self.get_matcher()
        self.matcher.activate()

    @staticmethod
    def get_matcher():
        """Return a myco matcher instance based on the global BidOffer match type."""
        if is_external_matching_enabled():
            return MycoExternalMatcher()
        else:
            return MycoInternalMatcher()

    def update_area_uuid_markets_mapping(self, area_uuid_markets_mapping: Dict[str, Dict]) -> None:
        """Interface for updating the area_uuid_markets_mapping of Myco matchers."""
        self.matcher.area_uuid_markets_mapping.update(area_uuid_markets_mapping)

    def match_recommendations(self, **kwargs) -> None:
        """Match bids/offers recommendations."""
        self.matcher.match_recommendations(**kwargs)

    def event_tick(self, **kwargs) -> None:
        """Handler for the tick event."""
        self.matcher.event_tick(**kwargs)

    def event_market_cycle(self, **kwargs) -> None:
        """Handler for the market_cycle event."""
        self.matcher.event_market_cycle(**kwargs)

    def event_finish(self, **kwargs) -> None:
        """Handler for the finish event."""
        self.matcher.event_finish(**kwargs)
