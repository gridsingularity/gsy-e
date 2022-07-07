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
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import BidOfferMatchAlgoEnum
from gsy_framework.matching_algorithms import (
    PayAsBidMatchingAlgorithm, PayAsClearMatchingAlgorithm,
    AttributedMatchingAlgorithm)

from gsy_e.gsy_e_core.enums import AvailableMarketTypes
from gsy_e.gsy_e_core.exceptions import WrongMarketTypeException
from gsy_e.gsy_e_core.global_objects_singleton import global_objects
from gsy_e.gsy_e_core.market_counters import (DayForwardMarketCounter, WeekForwardMarketCounter,
                                              MonthForwardMarketCounter, YearForwardMarketCounter)
from gsy_e.models.myco_matcher.myco_matcher_interface import MycoMatcherInterface


class MycoInternalMatcher(MycoMatcherInterface):
    """Interface for market matching, set the matching algorithm and expose recommendations."""

    def __init__(self):
        super().__init__()
        self.match_algorithm = None
        # TBD: Which matching algorithm is applied for which forward market type
        self._forward_match_algorithms = {
            AvailableMarketTypes.DAY_FORWARD: PayAsBidMatchingAlgorithm,
            AvailableMarketTypes.WEEK_FORWARD: PayAsClearMatchingAlgorithm,
            AvailableMarketTypes.MONTH_FORWARD: PayAsClearMatchingAlgorithm,
            AvailableMarketTypes.YEAR_FORWARD: PayAsClearMatchingAlgorithm,
        }
        self._forward_market_counters = {
            AvailableMarketTypes.DAY_FORWARD: DayForwardMarketCounter,
            AvailableMarketTypes.WEEK_FORWARD: WeekForwardMarketCounter,
            AvailableMarketTypes.MONTH_FORWARD: MonthForwardMarketCounter,
            AvailableMarketTypes.YEAR_FORWARD: YearForwardMarketCounter
        }

    def activate(self):
        self.match_algorithm = self._get_matching_algorithm_spot_markets()

    def _get_matches_recommendations(self, data):
        """Wrapper for matching algorithm's matches recommendations."""
        return self.match_algorithm.get_matches_recommendations(data)

    @staticmethod
    def _get_matching_algorithm_spot_markets():
        """Return a matching algorithm instance based on the global BidOffer match type.

        :raises:
            WrongMarketTypeException
        """
        if (ConstSettings.MASettings.BID_OFFER_MATCH_TYPE ==
                BidOfferMatchAlgoEnum.PAY_AS_BID.value):
            return PayAsBidMatchingAlgorithm()
        if (ConstSettings.MASettings.BID_OFFER_MATCH_TYPE ==
                BidOfferMatchAlgoEnum.PAY_AS_CLEAR.value):
            return PayAsClearMatchingAlgorithm()
        if (ConstSettings.MASettings.BID_OFFER_MATCH_TYPE ==
                BidOfferMatchAlgoEnum.DOF.value):
            return AttributedMatchingAlgorithm()
        raise WrongMarketTypeException("Wrong market type setting flag "
                                       f"{ConstSettings.MASettings.MARKET_TYPE}")

    def match_recommendations(self, **kwargs):
        """Request trade recommendations and match them in the relevant market."""
        for area_uuid, area_data in self.area_uuid_markets_mapping.items():
            markets = [*area_data[AvailableMarketTypes.SPOT],
                       *area_data[AvailableMarketTypes.SETTLEMENT]]
            if global_objects.future_market_counter.is_time_for_clearing(
                    area_data["current_time"]):
                markets.append(area_data[AvailableMarketTypes.FUTURE])
            self._match_recommendations(area_uuid, area_data, markets,
                                        self._get_matches_recommendations)
        self.area_uuid_markets_mapping = {}

    def event_tick(self, **kwargs) -> None:
        pass

    def event_market_cycle(self, **kwargs) -> None:
        pass

    def event_finish(self, **kwargs) -> None:
        pass
