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
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.matching_algorithms import (PayAsBidMatchingAlgorithm,
                                               PayAsClearMatchingAlgorithm)

from gsy_e.gsy_e_core.market_counters import (DayForwardMarketCounter, IntraDayMarketCounter,
                                              MonthForwardMarketCounter, WeekForwardMarketCounter,
                                              YearForwardMarketCounter)
from gsy_e.models.matching_engine_matcher.matching_engine_matcher_interface import \
    MatchingEngineMatcherInterface


class MatchingEngineInternalForwardMarketMatcher(MatchingEngineMatcherInterface):
    """MatchingEngine matcher that deals with matching in the forward markets."""

    def __init__(self):
        super().__init__()

        self._forward_match_algorithms = {
            AvailableMarketTypes.INTRADAY: PayAsBidMatchingAlgorithm,
            AvailableMarketTypes.DAY_FORWARD: PayAsBidMatchingAlgorithm,
            AvailableMarketTypes.WEEK_FORWARD: PayAsClearMatchingAlgorithm,
            AvailableMarketTypes.MONTH_FORWARD: PayAsClearMatchingAlgorithm,
            AvailableMarketTypes.YEAR_FORWARD: PayAsClearMatchingAlgorithm,
        }
        self._forward_market_counters = {
            AvailableMarketTypes.INTRADAY: IntraDayMarketCounter,
            AvailableMarketTypes.DAY_FORWARD: DayForwardMarketCounter,
            AvailableMarketTypes.WEEK_FORWARD: WeekForwardMarketCounter,
            AvailableMarketTypes.MONTH_FORWARD: MonthForwardMarketCounter,
            AvailableMarketTypes.YEAR_FORWARD: YearForwardMarketCounter
        }

    def activate(self):
        pass

    def match_recommendations(self, **kwargs):
        for area_uuid, area_data in self.area_uuid_markets_mapping.items():
            for market_type, matching_algorithm in self._forward_match_algorithms.items():
                if self._forward_market_counters[market_type].is_time_for_clearing(
                        area_data["current_time"]) and market_type in area_data:
                    self._match_recommendations(
                        area_uuid, area_data, [area_data[market_type]],
                        matching_algorithm().get_matches_recommendations)
        self.area_uuid_markets_mapping = {}

    def event_tick(self, **kwargs) -> None:
        pass

    def event_market_cycle(self, **kwargs) -> None:
        pass

    def event_finish(self, **kwargs) -> None:
        pass
