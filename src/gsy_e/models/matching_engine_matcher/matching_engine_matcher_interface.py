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
from abc import ABC, abstractmethod
from typing import Dict, List, Callable


class MatchingEngineMatcherInterface(ABC):
    """Interface for matching engine matchers' public methods."""
    def __init__(self):
        self.area_uuid_markets_mapping: Dict[str, Dict] = {}

    def activate(self):
        """Method to be called upon the activation of MatchingEngineMatcher."""

    def update_area_uuid_markets_mapping(self, area_uuid_markets_mapping: Dict[str, Dict]) -> None:
        """Interface for updating the area_uuid_markets_mapping of Matching Engine matchers."""
        self.area_uuid_markets_mapping.update(area_uuid_markets_mapping)

    @abstractmethod
    def match_recommendations(self, **kwargs) -> None:
        """Match bids/offers recommendations."""

    def event_tick(self, **kwargs) -> None:
        """Handler for the tick event."""

    def event_market_cycle(self, **kwargs) -> None:
        """Handler for the market_cycle event."""

    def event_finish(self, **kwargs) -> None:
        """Handler for the finish event."""

    @staticmethod
    def _match_recommendations(area_uuid: str, area_data: Dict, markets: List,
                               get_matches_recommendations: Callable) -> None:
        """Request trade recommendations and match them in the relevant market."""
        for market in markets:
            if not market:
                continue
            if market.no_new_order:
                continue
            while True:
                # Perform matching until all recommendations and their residuals are handled.
                orders = market.orders_per_slot()

                # Format should be: {area_uuid: {time_slot: {"bids": [], "offers": [], ...}}}
                data = {
                    area_uuid: {
                        time_slot: {**orders_data, "current_time": area_data["current_time"]}
                        for time_slot, orders_data in orders.items()}}
                bid_offer_pairs = get_matches_recommendations(data)
                if not bid_offer_pairs:
                    break
                trades_occurred = market.match_recommendations(bid_offer_pairs)
                if not trades_occurred:
                    break
            market.no_new_order = True
