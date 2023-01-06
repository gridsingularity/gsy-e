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
from gsy_framework.data_classes import Bid, Offer, Trade, TraderDetails
from pendulum import datetime, duration

from gsy_e.models.area import Area
from gsy_e.models.area.market_rotators import (DayForwardMarketRotator, IntradayMarketRotator,
                                               WeekForwardMarketRotator, MonthForwardMarketRotator,
                                               YearForwardMarketRotator)
from gsy_e.models.market.forward import (ForwardMarketBase, DayForwardMarket, IntradayMarket,
                                         WeekForwardMarket, MonthForwardMarket, YearForwardMarket)


from tests.market import count_orders_in_buffers

CURRENT_MARKET_SLOT = datetime(2022, 6, 13, 0, 0)  # day of week = 1 (Monday)


class TestForwardMarkets:

    @staticmethod
    def _create_forward_market(market_class: ForwardMarketBase, create=False):
        area = MagicMock(spec=Area)
        area.config.start_date = CURRENT_MARKET_SLOT
        area.config.end_date = area.config.start_date.add(years=6)
        area.activate()
        forward_markets = market_class(bc=area.bc)
        if create:
            forward_markets.create_future_market_slots(CURRENT_MARKET_SLOT, area.config)
        return forward_markets

    @pytest.mark.parametrize("market_class, expected_market_count",
                             [[IntradayMarket, 24 * 4 - 1],
                              [DayForwardMarket, 24 * 7 - 1],
                              [WeekForwardMarket, 52 - 1],
                              [MonthForwardMarket, 24 - 1],
                              [YearForwardMarket, 5]])
    @patch("gsy_e.models.market.future.is_time_slot_in_simulation_duration", MagicMock())
    def test_create_forward_markets(self, market_class, expected_market_count):
        # pylint: disable=protected-access

        area = Area("test_area")
        with patch("gsy_e.models.market.forward.ConstSettings.ForwardMarketSettings."
                   "ENABLE_FORWARD_MARKETS", False):
            forward_markets = self._create_forward_market(market_class)
            forward_markets.create_future_market_slots(CURRENT_MARKET_SLOT, area.config)
            assert not hasattr(forward_markets, "_bids")
            assert not hasattr(forward_markets, "_offers")

        with patch("gsy_e.models.market.forward.ConstSettings.ForwardMarketSettings."
                   "ENABLE_FORWARD_MARKETS", True):
            forward_markets = self._create_forward_market(market_class)
            forward_markets.create_future_market_slots(CURRENT_MARKET_SLOT, area.config)
            for buffer in [forward_markets.slot_bid_mapping,
                           forward_markets.slot_offer_mapping,
                           forward_markets.slot_trade_mapping]:

                assert len(buffer.keys()) == expected_market_count
                ahead_time_slot = market_class._get_start_time(CURRENT_MARKET_SLOT, area.config)
                most_future_slot = market_class._get_end_time(CURRENT_MARKET_SLOT)
                assert all(ahead_time_slot <= time_slot <= most_future_slot
                           for time_slot in buffer)
                if market_class == DayForwardMarket:
                    assert all(time_slot.minute == 0 for time_slot in buffer)
                if market_class == WeekForwardMarket:
                    assert all(time_slot.hour == 0 and time_slot.minute == 0
                               for time_slot in buffer)
                if market_class == MonthForwardMarket:
                    assert all(time_slot.day == 1 for time_slot in buffer)
                if market_class == YearForwardMarket:
                    assert all(time_slot.month == 1 and time_slot.day == 1 for time_slot in buffer)

    @pytest.mark.parametrize("market_class, rotator_class, expected_market_count, rotation_time",
                             [[IntradayMarket, IntradayMarketRotator, 24 * 4 - 1,
                               CURRENT_MARKET_SLOT.set(minute=15)],
                              [DayForwardMarket, DayForwardMarketRotator, 24 * 7 - 1,
                               CURRENT_MARKET_SLOT.add(hours=1)],
                              [WeekForwardMarket, WeekForwardMarketRotator, 51,
                               CURRENT_MARKET_SLOT.add(weeks=1)],
                              [MonthForwardMarket, MonthForwardMarketRotator, 23,
                               CURRENT_MARKET_SLOT.set(day=1).add(months=1)],
                              [YearForwardMarket, YearForwardMarketRotator, 5,
                               CURRENT_MARKET_SLOT.set(day=1, month=1).add(years=1)]
                              ])
    @patch("gsy_e.models.market.forward.ConstSettings.ForwardMarketSettings."
           "ENABLE_FORWARD_MARKETS", True)
    def test_market_rotation(self, market_class, rotator_class, expected_market_count,
                             rotation_time):
        forward_markets = self._create_forward_market(market_class, create=True)
        for time_slot in forward_markets.slot_bid_mapping:
            bid = Bid(f"bid{time_slot}", time_slot, 1, 1, TraderDetails("buyer", ""),
                      time_slot=time_slot)
            forward_markets.bids[bid.id] = bid
            offer = Offer(f"oid{time_slot}", time_slot, 1, 1, TraderDetails("seller", ""),
                          time_slot=time_slot)
            forward_markets.offers[offer.id] = offer
            trade = Trade(f"tid{time_slot}", time_slot, TraderDetails("seller", ""),
                          TraderDetails("buyer", ""), offer=offer,
                          time_slot=time_slot, traded_energy=1, trade_price=1)
            forward_markets.trades.append(trade)

        rotator = rotator_class(forward_markets)
        count_orders_in_buffers(forward_markets, expected_market_count)
        # Markets should not be deleted when it is not time
        rotator.rotate(CURRENT_MARKET_SLOT.add(minutes=5))
        count_orders_in_buffers(forward_markets, expected_market_count)
        # Market should be deleted if the rotation time has been reached
        rotator.rotate(rotation_time)
        count_orders_in_buffers(forward_markets, expected_market_count - 1)

    # pylint: disable=too-many-arguments
    @pytest.mark.parametrize("market_class, expected_market_count, start_timedelta, "
                             "delivery_duration, closing_delivery_timedelta, reference_time",
                             [[IntradayMarket, 24 * 4 - 1, duration(minutes=30),
                               duration(minutes=15), duration(minutes=15), CURRENT_MARKET_SLOT],
                              [DayForwardMarket, 24 * 7 - 1, duration(days=1, hours=1),
                               duration(hours=1), duration(days=1), CURRENT_MARKET_SLOT],
                              [WeekForwardMarket, 51, duration(weeks=2),
                               duration(weeks=1), duration(weeks=1), CURRENT_MARKET_SLOT],
                              [MonthForwardMarket, 23, duration(months=2),
                               duration(months=1), duration(months=1),
                               CURRENT_MARKET_SLOT.set(day=1, hour=0, minute=0)],
                              [YearForwardMarket, 5, duration(years=2),
                               duration(years=1), duration(years=1),
                               CURRENT_MARKET_SLOT.set(month=1, day=1, hour=0, minute=0)]
                              ])
    @patch("gsy_e.models.market.forward.ConstSettings.ForwardMarketSettings."
           "ENABLE_FORWARD_MARKETS", True)
    def test_forward_market_parameters(
            self, market_class, expected_market_count, start_timedelta, delivery_duration,
            closing_delivery_timedelta, reference_time
    ):
        forward_markets = self._create_forward_market(market_class, create=True)
        slots_info = forward_markets.open_market_slot_info
        assert len(slots_info) == expected_market_count

        expected_open_time = CURRENT_MARKET_SLOT
        # Reference time is the time that the markets use as a reference in order to calculate the
        # slots they need to open. For instance, reference time for the yearly market is always the
        # first hour of the first day of the current year, while for the monthly market is the
        # first hour of the first day of the current month.
        expected_delivery_time = reference_time + start_timedelta
        for delivery_time, slot_info in slots_info.items():
            assert delivery_time == expected_delivery_time
            assert slot_info.delivery_start_time == expected_delivery_time
            assert slot_info.delivery_end_time == expected_delivery_time + delivery_duration
            assert slot_info.opening_time == expected_open_time
            assert slot_info.closing_time == expected_delivery_time - closing_delivery_timedelta
            expected_delivery_time = expected_delivery_time + delivery_duration
