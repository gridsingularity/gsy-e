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

from d3a_interface.enums import BidOfferMatchAlgoEnum
from d3a_interface.constants_limits import ConstSettings
from d3a_interface.matching_algorithms import (
    PayAsBidMatchingAlgorithm, PayAsClearMatchingAlgorithm
)
from d3a.d3a_core.exceptions import WrongMarketTypeException
from d3a.models.myco_matcher.myco_matcher_interface import MycoMatcherInterface


class MycoInternalMatcher(MycoMatcherInterface):
    """Interface for market matching, set the matching algorithm and expose recommendations."""

    def __init__(self):
        super().__init__()
        self.match_algorithm = None

    def activate(self):
        self.match_algorithm = self.get_matching_algorithm()

    def _get_matches_recommendations(self, data):
        """Wrapper for matching algorithm's matches recommendations."""
        return self.match_algorithm.get_matches_recommendations(data)

    @staticmethod
    def get_matching_algorithm():
        """Return a matching algorithm instance based on the global BidOffer match type.

        :raises:
            WrongMarketTypeException
        """
        if (ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE ==
                BidOfferMatchAlgoEnum.PAY_AS_BID.value):
            return PayAsBidMatchingAlgorithm()
        if (ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE ==
                BidOfferMatchAlgoEnum.PAY_AS_CLEAR.value):
            return PayAsClearMatchingAlgorithm()
        raise WrongMarketTypeException("Wrong market type setting flag "
                                       f"{ConstSettings.IAASettings.MARKET_TYPE}")

    def match_recommendations(self, **kwargs):
        """Request trade recommendations and match them in the relevant market."""
        for area_uuid, area_data in self.area_uuid_markets_mapping.items():
            # TODO: we don't always want to clear future markets
            markets = [*area_data["markets"], *area_data["settlement_markets"],
                       area_data["future_markets"]]
            for market in markets:
                while True:
                    orders = market.orders_per_slot()
                    # Format should be: {area_uuid: {time_slot: {"bids": [], "offers": [], ...}}}
                    data = {
                        area_uuid: {
                            time_slot: {**orders_data, "current_time": area_data["current_time"]}
                            for time_slot, orders_data in orders.items()}}
                    bid_offer_pairs = self._get_matches_recommendations(data)
                    if not bid_offer_pairs:
                        break
                    market.match_recommendations(bid_offer_pairs)

        self.area_uuid_markets_mapping = {}

    def event_tick(self, **kwargs) -> None:
        pass

    def event_market_cycle(self, **kwargs) -> None:
        pass

    def event_finish(self, **kwargs) -> None:
        pass
