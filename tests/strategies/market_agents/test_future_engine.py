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

from typing import Generator
from unittest.mock import MagicMock

import pytest
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import Offer, Bid
from pendulum import datetime, now

from gsy_e.models.market.future import FutureMarkets
from gsy_e.models.strategy.market_agents.future_agent import FutureAgent
from gsy_e.models.strategy.market_agents.future_engine import FutureEngine
from gsy_e.models.strategy.market_agents.one_sided_engine import OfferInfo
from gsy_e.models.strategy.market_agents.two_sided_engine import BidInfo

CURRENT_TIME_SLOT = datetime(2021, 10, 21, 0, 0)


@pytest.fixture(name="future_engine")
def future_engine_fixture() -> Generator[FutureEngine, None, None]:
    """Return FutureAgent object"""
    original_future_markets_duration = (
        ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS)
    ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS = 24
    market_agent = MagicMock(autospec=FutureAgent)
    higher_market = MagicMock(autospec=FutureMarkets)
    lower_market = MagicMock(autospec=FutureMarkets)
    future_engine = FutureEngine(name="test_engine", min_bid_age=1, min_offer_age=1,
                                 owner=market_agent, market_1=higher_market, market_2=lower_market)
    yield future_engine
    ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS = (
        original_future_markets_duration)


class TestFutureEngine:
    """Collects tests for the FutureEngine."""

    @staticmethod
    def test_clean_up_order_buffers_removes_all_traces_of_unneeded_bids(
            future_engine: FutureEngine) -> None:
        """
        Test if all traces of old bids are removed and future bids traces are kept in buffers.
        """
        old_bid = Bid("old_id", now(), 123, 321, "A", time_slot=CURRENT_TIME_SLOT)
        forwarded_old_bid = Bid("fold_id", now(), 123, 321, "B", time_slot=CURRENT_TIME_SLOT)
        future_bid = Bid("future_id", now(), 123, 321, "A",
                         time_slot=CURRENT_TIME_SLOT.add(minutes=15))
        forwarded_future_bid = Bid("f_future_id", now(), 123, 321, "B",
                                   time_slot=CURRENT_TIME_SLOT.add(minutes=15))
        old_bid_info = BidInfo(old_bid, forwarded_old_bid)
        future_bid_info = BidInfo(future_bid, forwarded_future_bid)
        future_engine.forwarded_bids[old_bid.id] = old_bid_info
        future_engine.forwarded_bids[future_bid.id] = future_bid_info
        future_engine.bid_age[old_bid.id] = 1
        future_engine.bid_age[future_bid.id] = 1
        future_engine.bid_trade_residual[old_bid.id] = old_bid
        future_engine.bid_trade_residual[future_bid.id] = future_bid

        future_engine.clean_up_order_buffers(CURRENT_TIME_SLOT)

        assert len(future_engine.forwarded_bids) == 1
        assert next(iter(future_engine.forwarded_bids.values())) == future_bid_info
        assert len(future_engine.bid_trade_residual) == 1
        assert future_engine.bid_trade_residual == {future_bid.id: future_bid}
        assert future_engine.bid_age == {future_bid.id: 1}

    @staticmethod
    def test_clean_up_order_buffers_removes_all_traces_of_unneeded_offers(
            future_engine: FutureEngine) -> None:
        """
        Test if all traces of old offers are removed and future offers traces are kept in buffers.
        """
        old_offer = Offer("old_id", now(), 123, 321, "A", time_slot=CURRENT_TIME_SLOT)
        forwarded_old_offer = Offer("fold_id", now(), 123, 321, "B", time_slot=CURRENT_TIME_SLOT)
        future_offer = Offer("future_id", now(), 123, 321, "A",
                             time_slot=CURRENT_TIME_SLOT.add(minutes=15))
        forwarded_future_offer = Offer("f_future_id", now(), 123, 321, "B",
                                       time_slot=CURRENT_TIME_SLOT.add(minutes=15))
        old_offer_info = OfferInfo(old_offer, forwarded_old_offer)
        future_offer_info = OfferInfo(future_offer, forwarded_future_offer)
        future_engine.forwarded_offers[old_offer.id] = old_offer_info
        future_engine.forwarded_offers[future_offer.id] = future_offer_info
        future_engine.offer_age[old_offer.id] = 1
        future_engine.offer_age[future_offer.id] = 1
        future_engine.trade_residual[old_offer.id] = old_offer
        future_engine.trade_residual[future_offer.id] = future_offer

        future_engine.clean_up_order_buffers(CURRENT_TIME_SLOT)

        assert len(future_engine.forwarded_offers) == 1
        assert next(iter(future_engine.forwarded_offers.values())) == future_offer_info
        assert len(future_engine.trade_residual) == 1
        assert future_engine.trade_residual == {future_offer.id: future_offer}
        assert future_engine.offer_age == {future_offer.id: 1}
