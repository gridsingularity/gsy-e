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
import pytest  # noqa
from typing import Tuple

import pendulum
from d3a.models.market.market_structures import Bid, Offer, Trade
from d3a.models.market.two_sided import TwoSidedMarket
from d3a_interface.dataclasses import BidOfferMatch


class TestTwoSidedPACMatching:

    @staticmethod
    def _get_offer_bid_trades() -> Tuple[Trade, Trade]:
        offer_trade = Trade("trade", 1, Offer("offer_id", pendulum.now(), 1, 1, "S"), "S", "B",
                            residual=Offer("residual_offer", pendulum.now(), 0.5, 0.5, "S"))
        bid_trade = Trade("bid_trade", 1, Bid("bid_id2", pendulum.now(), 1, 1, "S"), "S", "B",
                          residual=Bid("residual_bid_2", pendulum.now(), 1, 1, "S"))
        return offer_trade, bid_trade

    def test_matching_list_gets_updated_with_residual_offers(self):
        matches = [
            BidOfferMatch(
                offer=Offer("offer_id", pendulum.now(), 1, 1, "S").serializable_dict(),
                selected_energy=1,
                bid=Bid("bid_id", pendulum.now(), 1, 1, "B").serializable_dict(), trade_rate=1,
                market_id="").serializable_dict(),
            BidOfferMatch(
                offer=Offer("offer_id2", pendulum.now(), 2, 2, "S").serializable_dict(),
                selected_energy=2,
                bid=Bid("bid_id2", pendulum.now(), 2, 2, "B").serializable_dict(), trade_rate=1,
                market_id="").serializable_dict()
        ]
        offer_trade, bid_trade = self._get_offer_bid_trades()

        matches = TwoSidedMarket._replace_offers_bids_with_residual_in_matching_list(
            matches, 0, offer_trade, bid_trade
        )
        assert len(matches) == 2
        assert matches[0]["offer"]["id"] == "residual_offer"
        assert matches[1]["bid"]["id"] == "residual_bid_2"

    def test_matching_list_affects_only_matches_after_start_index(self):
        matches = [
            BidOfferMatch(
                offer=Offer("offer_id", pendulum.now(), 1, 1, "S").serializable_dict(),
                selected_energy=1,
                bid=Bid("bid_id", pendulum.now(), 1, 1, "B").serializable_dict(), trade_rate=1,
                market_id="").serializable_dict(),
            BidOfferMatch(
                offer=Offer("offer_id2", pendulum.now(), 2, 2, "S").serializable_dict(),
                selected_energy=2,
                bid=Bid("bid_id2", pendulum.now(), 2, 2, "B").serializable_dict(), trade_rate=1,
                market_id="").serializable_dict(),
            BidOfferMatch(
                offer=Offer("offer_id", pendulum.now(), 1, 1, "S").serializable_dict(),
                selected_energy=1,
                bid=Bid("bid_id", pendulum.now(), 1, 1, "B").serializable_dict(), trade_rate=1,
                market_id="").serializable_dict()
        ]

        offer_trade, bid_trade = self._get_offer_bid_trades()

        matches = TwoSidedMarket._replace_offers_bids_with_residual_in_matching_list(
            matches, 1, offer_trade, bid_trade
        )
        assert len(matches) == 3
        assert matches[0]["offer"]["id"] == "offer_id"
        assert matches[1]["bid"]["id"] == "residual_bid_2"
        assert matches[2]["offer"]["id"] == "residual_offer"
