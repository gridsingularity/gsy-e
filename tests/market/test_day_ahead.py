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
from unittest.mock import patch, MagicMock

import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.data_classes import Bid, Offer, Trade
from pendulum import datetime

from gsy_e.models.area import Area
from gsy_e.models.area.market_rotators import DayAheadMarketRotator
from gsy_e.models.market import GridFee
from gsy_e.models.market.day_ahead import DayAheadMarkets
from gsy_e.models.market.future import FutureMarketException
from tests.market.test_future import count_orders_in_buffers

DEFAULT_CURRENT_MARKET_SLOT = datetime(2022, 6, 13, 0, 0)


@pytest.fixture(name="day_ahead_markets")
def active_day_ahead_market() -> DayAheadMarkets:
    """Fixture for activated day-ahead market."""
    orig_day_ahead_duration = ConstSettings.FutureMarketSettings.DAY_AHEAD_DURATION_DAYS
    orig_start_date = GlobalConfig.start_date
    area = Area("test_area")
    area.config.start_date = DEFAULT_CURRENT_MARKET_SLOT
    area.config.end_date = area.config.start_date.add(days=5)
    area.activate()
    day_ahead_markets = DayAheadMarkets(
            bc=area.bc,
            notification_listener=area.dispatcher.broadcast_notification,
            grid_fee_type=area.config.grid_fee_type,
            grid_fees=GridFee(grid_fee_percentage=area.grid_fee_percentage,
                              grid_fee_const=area.grid_fee_constant),
            name=area.name)
    day_ahead_markets.create_future_markets(DEFAULT_CURRENT_MARKET_SLOT, area.config)
    yield day_ahead_markets

    ConstSettings.FutureMarketSettings.DAY_AHEAD_DURATION_DAYS = orig_day_ahead_duration
    GlobalConfig.start_date = orig_start_date


class TestDayAhead:

    @staticmethod
    @patch("gsy_e.models.market.future.is_time_slot_in_simulation_duration", MagicMock())
    def test_create_day_ahead_future_markets(day_ahead_markets):
        day_ahead_markets.offers = {}
        day_ahead_markets.bids = {}
        area = Area("test_area")
        with patch("gsy_e.models.market.day_ahead.ConstSettings.FutureMarketSettings."
                   "DAY_AHEAD_DURATION_DAYS", 0):
            day_ahead_markets.create_future_markets(DEFAULT_CURRENT_MARKET_SLOT, area.config)
        for buffer in [day_ahead_markets.slot_bid_mapping,
                       day_ahead_markets.slot_offer_mapping,
                       day_ahead_markets.slot_trade_mapping]:
            assert len(buffer.keys()) == 0

        with patch("gsy_e.models.market.day_ahead.ConstSettings.FutureMarketSettings."
                   "DAY_AHEAD_DURATION_DAYS", 1):
            day_ahead_markets.create_future_markets(DEFAULT_CURRENT_MARKET_SLOT, area.config)
            for buffer in [day_ahead_markets.slot_bid_mapping,
                           day_ahead_markets.slot_offer_mapping,
                           day_ahead_markets.slot_trade_mapping]:
                assert len(buffer.keys()) == 24
                day_ahead_time_slot = DEFAULT_CURRENT_MARKET_SLOT.add(days=1)
                most_future_slot = (day_ahead_time_slot.add(
                    days=ConstSettings.FutureMarketSettings.DAY_AHEAD_DURATION_DAYS,
                    minutes=-ConstSettings.FutureMarketSettings.DAY_AHEAD_MARKET_LENGTH_MINUTES))
                assert all(day_ahead_time_slot <= time_slot <= most_future_slot
                           for time_slot in buffer)

    @staticmethod
    def test_offer_is_posted_correctly(day_ahead_markets):
        first_day_ahead_market = next(iter(day_ahead_markets.slot_offer_mapping))
        offer = day_ahead_markets.offer(1, 1, "seller", "seller_origin",
                                        time_slot=first_day_ahead_market)
        assert len(day_ahead_markets.offers) == 1
        assert offer in day_ahead_markets.offers.values()
        assert len(day_ahead_markets.slot_offer_mapping[first_day_ahead_market]) == 1
        assert offer in day_ahead_markets.slot_offer_mapping[first_day_ahead_market]

    @staticmethod
    def test_offer_is_not_posted_if_time_slot_not_provided(day_ahead_markets):
        with pytest.raises(FutureMarketException):
            day_ahead_markets.offer(1, 1, "seller", "seller_origin")

    @staticmethod
    def test_bids_is_posted_correctly(day_ahead_markets):
        first_future_market = next(iter(day_ahead_markets.slot_bid_mapping))
        bid = day_ahead_markets.bid(1, 1, "buyer", "buyer_origin", time_slot=first_future_market)
        assert len(day_ahead_markets.bids) == 1
        assert bid in day_ahead_markets.bids.values()
        assert len(day_ahead_markets.slot_bid_mapping[first_future_market]) == 1
        assert bid in day_ahead_markets.slot_bid_mapping[first_future_market]

    @staticmethod
    def test_bid_is_not_posted_if_time_slot_not_provided(day_ahead_markets):
        with pytest.raises(FutureMarketException):
            day_ahead_markets.bid(1, 1, "seller", "seller_origin")

    @staticmethod
    def test_delete_offer(day_ahead_markets):
        first_future_market = next(iter(day_ahead_markets.slot_offer_mapping))
        offer = day_ahead_markets.offer(1, 1, "seller", "seller_origin",
                                        time_slot=first_future_market)
        day_ahead_markets.delete_offer(offer)
        assert len(day_ahead_markets.offers) == 0
        assert len(day_ahead_markets.slot_offer_mapping[first_future_market]) == 0

    @staticmethod
    def test_delete_offer_via_offer_id(day_ahead_markets):
        first_future_market = next(iter(day_ahead_markets.slot_offer_mapping))
        offer = day_ahead_markets.offer(1, 1, "seller", "seller_origin",
                                        time_slot=first_future_market)
        day_ahead_markets.delete_offer(offer.id)
        assert len(day_ahead_markets.offers) == 0
        assert len(day_ahead_markets.slot_offer_mapping[first_future_market]) == 0

    @staticmethod
    def test_delete_bid(day_ahead_markets):
        first_future_market = next(iter(day_ahead_markets.slot_bid_mapping))
        bid = day_ahead_markets.bid(1, 1, "buyer", "seller_origin",
                                    time_slot=first_future_market)
        day_ahead_markets.delete_bid(bid)
        assert len(day_ahead_markets.bids) == 0
        assert len(day_ahead_markets.slot_bid_mapping[first_future_market]) == 0


class TestDayAheadMarketRotator:

    @staticmethod
    def test_market_rotation(day_ahead_markets):
        for time_slot in day_ahead_markets.slot_bid_mapping:
            bid = Bid(f"bid{time_slot}", time_slot, 1, 1, "buyer", time_slot=time_slot)
            day_ahead_markets.bids[bid.id] = bid
            offer = Offer(f"oid{time_slot}", time_slot, 1, 1, "seller", time_slot=time_slot)
            day_ahead_markets.offers[offer.id] = offer
            trade = Trade(f"tid{time_slot}", time_slot, offer, "seller", "buyer",
                          time_slot=time_slot, traded_energy=1, trade_price=1)
            day_ahead_markets.trades.append(trade)

        rotator = DayAheadMarketRotator(day_ahead_markets)
        count_orders_in_buffers(day_ahead_markets, 24)
        # Markets should not be deleted when it is not time
        rotator.rotate(DEFAULT_CURRENT_MARKET_SLOT)
        count_orders_in_buffers(day_ahead_markets, 24)
        # Market should be deleted if the DAY_AHEAD_CLEARING_DAYTIME_HOUR is reached
        rotator.rotate(DEFAULT_CURRENT_MARKET_SLOT.set(
            hour=ConstSettings.FutureMarketSettings.DAY_AHEAD_CLEARING_DAYTIME_HOUR))
        count_orders_in_buffers(day_ahead_markets, 0)
