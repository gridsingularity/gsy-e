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
import pytest
from gsy_framework.constants_limits import GlobalConfig, DATE_TIME_FORMAT
from gsy_framework.data_classes import Bid, Offer, Trade, TradeBidOfferInfo
from gsy_framework.utils import datetime_to_string_incl_seconds
from pendulum import datetime, duration, now

from gsy_e.models.area import Area
from gsy_e.models.market import GridFee
from gsy_e.models.market.future import FutureMarkets, FutureMarketException

DEFAULT_CURRENT_MARKET_SLOT = datetime(2021, 10, 19, 0, 0)
DEFAULT_SLOT_LENGTH = duration(minutes=15)


@pytest.fixture(name="future_market")
def active_future_market() -> FutureMarkets:
    """Return future market object."""
    orig_future_market_duration = GlobalConfig.FUTURE_MARKET_DURATION_HOURS
    orig_start_date = GlobalConfig.start_date
    GlobalConfig.FUTURE_MARKET_DURATION_HOURS = 1
    area = Area("test_area")
    area.config.start_date = DEFAULT_CURRENT_MARKET_SLOT
    area.config.end_date = area.config.start_date + area.config.sim_duration
    area.activate()
    future_market = FutureMarkets(
            bc=area.bc,
            notification_listener=area.dispatcher.broadcast_notification,
            grid_fee_type=area.config.grid_fee_type,
            grid_fees=GridFee(grid_fee_percentage=area.grid_fee_percentage,
                              grid_fee_const=area.grid_fee_constant),
            name=area.name)
    future_market.create_future_markets(
        DEFAULT_CURRENT_MARKET_SLOT, DEFAULT_SLOT_LENGTH, area.config)
    yield future_market

    GlobalConfig.FUTURE_MARKET_DURATION_HOURS = orig_future_market_duration
    GlobalConfig.start_date = orig_start_date


def count_orders_in_buffers(future_markets: FutureMarkets, expected_count: int) -> None:
    """Count number of markets and orders created in buffers."""
    for buffer in [future_markets.slot_bid_mapping,
                   future_markets.slot_offer_mapping,
                   future_markets.slot_trade_mapping]:
        assert all(len(orders) == 1 for orders in buffer.values())
        assert len(buffer) == expected_count
    assert len(future_markets.bids) == expected_count
    assert len(future_markets.offers) == expected_count
    assert len(future_markets.trades) == expected_count


class TestFutureMarkets:
    """Tests that target the future markets."""

    @staticmethod
    def test_create_future_markets(future_market):
        """Test if all future time_slots are created in the order buffers."""
        for buffer in [future_market.slot_bid_mapping,
                       future_market.slot_offer_mapping,
                       future_market.slot_trade_mapping]:
            assert len(buffer.keys()) == 5
            future_time_slot = DEFAULT_CURRENT_MARKET_SLOT.add(
                minutes=DEFAULT_SLOT_LENGTH.total_minutes())
            most_future_slot = (future_time_slot +
                                duration(hours=GlobalConfig.FUTURE_MARKET_DURATION_HOURS))
            assert all(future_time_slot <= time_slot <= most_future_slot for time_slot in buffer)

    @staticmethod
    def test_delete_old_future_markets(future_market):
        """Test if the correct markets slot buffers and their contents are deleted."""
        for time_slot in future_market.slot_bid_mapping:
            bid = Bid(f"bid{time_slot}", time_slot, 1, 1, "buyer", time_slot=time_slot)
            future_market.bids[bid.id] = bid
            offer = Offer(f"oid{time_slot}", time_slot, 1, 1, "seller", time_slot=time_slot)
            future_market.offers[offer.id] = offer
            trade = Trade(f"tid{time_slot}", time_slot, offer, "seller", "buyer",
                          time_slot=time_slot)
            future_market.trades.append(trade)

        count_orders_in_buffers(future_market, 5)
        first_future_market = next(iter(future_market.slot_bid_mapping))
        future_market.delete_orders_in_old_future_markets(first_future_market)
        count_orders_in_buffers(future_market, 4)

    @staticmethod
    def test_offer_is_posted_correctly(future_market):
        """Test if bid method posts bid correctly in the future markets buffers"""
        first_future_market = next(iter(future_market.slot_offer_mapping))
        offer = future_market.offer(1, 1, "seller", "seller_origin", time_slot=first_future_market)
        assert len(future_market.offers) == 1
        assert offer in future_market.offers.values()
        assert len(future_market.slot_offer_mapping[first_future_market]) == 1
        assert offer in future_market.slot_offer_mapping[first_future_market]

    @staticmethod
    def test_offer_is_not_posted_if_time_slot_not_provided(future_market):
        """Test if offer method raises Exception if time_slot not provided."""
        with pytest.raises(FutureMarketException):
            future_market.offer(1, 1, "seller", "seller_origin")

    @staticmethod
    def test_bids_is_posted_correctly(future_market):
        """Test if offer method posts bid correctly in the future markets buffers"""
        first_future_market = next(iter(future_market.slot_bid_mapping))
        bid = future_market.bid(1, 1, "buyer", "buyer_origin", time_slot=first_future_market)
        assert len(future_market.bids) == 1
        assert bid in future_market.bids.values()
        assert len(future_market.slot_bid_mapping[first_future_market]) == 1
        assert bid in future_market.slot_bid_mapping[first_future_market]

    @staticmethod
    def test_bid_is_not_posted_if_time_slot_not_provided(future_market):
        """Test if offer method raises Exception if time_slot not provided."""
        with pytest.raises(FutureMarketException):
            future_market.bid(1, 1, "seller", "seller_origin")

    @staticmethod
    def test_delete_offer(future_market):
        """Test if offer gets deleted from all buffers when calling delete_offer."""
        first_future_market = next(iter(future_market.slot_offer_mapping))
        offer = future_market.offer(1, 1, "seller", "seller_origin", time_slot=first_future_market)
        future_market.delete_offer(offer)
        assert len(future_market.offers) == 0
        assert len(future_market.slot_offer_mapping[first_future_market]) == 0

    @staticmethod
    def test_delete_offer_via_offer_id(future_market):
        """
        Test if offer gets deleted from all buffers when calling delete_offer using the offer_id.
        """
        first_future_market = next(iter(future_market.slot_offer_mapping))
        offer = future_market.offer(1, 1, "seller", "seller_origin", time_slot=first_future_market)
        future_market.delete_offer(offer.id)
        assert len(future_market.offers) == 0
        assert len(future_market.slot_offer_mapping[first_future_market]) == 0

    @staticmethod
    def test_delete_bid(future_market):
        """Test if bid gets deleted from all buffers when calling delete_bid."""
        first_future_market = next(iter(future_market.slot_bid_mapping))
        bid = future_market.bid(1, 1, "buyer", "seller_origin", time_slot=first_future_market)
        future_market.delete_bid(bid)
        assert len(future_market.bids) == 0
        assert len(future_market.slot_bid_mapping[first_future_market]) == 0

    @staticmethod
    def test_delete_bid_via_bid_id(future_market):
        """
        Test if bid gets deleted from all buffers when calling delete_bid using the bid_id.
        """
        first_future_market = next(iter(future_market.slot_bid_mapping))
        bid = future_market.bid(1, 1, "buyer", "seller_origin", time_slot=first_future_market)
        future_market.delete_bid(bid.id)
        assert len(future_market.bids) == 0
        assert len(future_market.slot_bid_mapping[first_future_market]) == 0

    @staticmethod
    def test_accept_bid(future_market):
        """Test if trade is added to trade buffers when accept_bid is called."""
        first_future_market = next(iter(future_market.slot_bid_mapping))
        bid = future_market.bid(1, 1, "buyer", "seller_origin", time_slot=first_future_market)
        trade = future_market.accept_bid(bid, 1, trade_offer_info=TradeBidOfferInfo(1, 1, 1, 1, 1))

        assert len(future_market.trades) == 1
        assert trade in future_market.trades
        assert len(future_market.slot_trade_mapping[first_future_market]) == 1
        assert trade in future_market.slot_trade_mapping[first_future_market]

    @staticmethod
    def test_accept_offer(future_market):
        """Test if trade is added to trade buffers when accept_offer is called."""
        first_future_market = next(iter(future_market.slot_bid_mapping))
        offer = future_market.offer(1, 1, "seller", "seller_origin", time_slot=first_future_market)
        trade = future_market.accept_offer(offer, "buyer")

        assert len(future_market.trades) == 1
        assert trade in future_market.trades
        assert len(future_market.slot_trade_mapping[first_future_market]) == 1
        assert trade in future_market.slot_trade_mapping[first_future_market]

    @staticmethod
    def test_orders_per_slot(future_market):
        """Test whether the orders_per_slot method returns order in format format."""
        time_slot1 = now()
        time_slot2 = time_slot1.add(minutes=15)
        future_market.bids = {"bid1": Bid(
            "bid1", time_slot1, 10, 10, "buyer", time_slot=time_slot1)}
        future_market.offers = {"offer1": Offer(
            "offer1", time_slot2, 10, 10, "seller", time_slot=time_slot2)}
        assert future_market.orders_per_slot() == {
            time_slot1.format(DATE_TIME_FORMAT): {
                "bids": [{"attributes": None,
                          "buyer": "buyer",
                          "buyer_id": None,
                          "buyer_origin": None,
                          "buyer_origin_id": None,
                          "energy": 10,
                          "energy_rate": 1.0,
                          "id": "bid1",
                          "original_price": 10,
                          "requirements": None,
                          "time_slot": datetime_to_string_incl_seconds(time_slot1),
                          "creation_time": datetime_to_string_incl_seconds(time_slot1),
                          "type": "Bid"}],
                "offers": []},
            time_slot2.format(DATE_TIME_FORMAT): {
                "bids": [],
                "offers": [{"attributes": None,
                            "energy": 10,
                            "energy_rate": 1.0,
                            "id": "offer1",
                            "original_price": 10,
                            "requirements": None,
                            "time_slot": datetime_to_string_incl_seconds(time_slot2),
                            "seller": "seller",
                            "seller_id": None,
                            "seller_origin": None,
                            "seller_origin_id": None,
                            "creation_time": datetime_to_string_incl_seconds(time_slot2),
                            "type": "Offer"}]}}
