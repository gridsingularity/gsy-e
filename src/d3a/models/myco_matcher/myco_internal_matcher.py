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
            for market_type in ["markets", "settlement_markets"]:
                for market in area_data[market_type]:
                    if not market:
                        continue
                    while True:
                        bids, offers = market.open_bids_and_offers()
                        data = {
                            area_uuid: {
                                market.time_slot_str:
                                    {"bids": [bid.serializable_dict() for bid in bids],
                                     "offers": [offer.serializable_dict() for offer in offers],
                                     "current_time": area_data["current_time"]}}}
                        bid_offer_pairs = self._get_matches_recommendations(data)
                        if not bid_offer_pairs:
                            break
                        market.match_recommendations(bid_offer_pairs)

        self._match_recommendations_future_markets()

        self.area_uuid_markets_mapping = {}

    def _match_recommendations_future_markets(self):
        """Loop over all future markets and match bids and offers."""
        for area_uuid, area_data in self.area_uuid_markets_mapping.items():
            future_markets = area_data["future_markets"]
            if not future_markets:
                continue
            for time_slot in future_markets.market_time_slots:
                while True:
                    bids, offers = future_markets.open_bids_and_offers(time_slot=time_slot)
                    data = {
                        area_uuid: {
                            time_slot:
                            {"bids": [bid.serializable_dict() for bid in bids],
                             "offers": [offer.serializable_dict() for offer in offers],
                             "current_time": area_data["current_time"]}
                        }
                    }
                    bid_offer_pairs = self._get_matches_recommendations(data)
                    if not bid_offer_pairs:
                        break
                    future_markets.match_recommendations(bid_offer_pairs)

    def event_tick(self, **kwargs) -> None:
        pass

    def event_market_cycle(self, **kwargs) -> None:
        pass

    def event_finish(self, **kwargs) -> None:
        pass
