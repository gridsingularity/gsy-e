# pylint: disable=protected-access
import json
import unittest
from concurrent.futures import Future, wait
from unittest.mock import MagicMock

from deepdiff import DeepDiff
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import Offer, Trade, Bid, TraderDetails
from pendulum import now, datetime

import gsy_e.models.market.market_redis_connection
from gsy_e.events import MarketEvent
from gsy_e.models.market.market_redis_connection import (
    MarketRedisEventPublisher, MarketRedisEventSubscriber, TwoSidedMarketRedisEventSubscriber)
from gsy_e.models.market.one_sided import OneSidedMarket

gsy_e.models.market.market_redis_connection.BlockingCommunicator = MagicMock
gsy_e.models.market.market_redis_connection.ResettableCommunicator = MagicMock

test_datetime = datetime(2021, 11, 3, 14, 0)


class TestMarketRedisEventPublisher(unittest.TestCase):

    def setUp(self):
        self.publisher = MarketRedisEventPublisher("test_id")

    def tearDown(self):
        pass

    def test_response_callback_stores_transaction_uuid(self):
        payload = {
            "data": json.dumps({
                "response": {},
                "transaction_uuid": "my_uuid"
            })
        }
        self.publisher.response_callback(payload)
        assert "my_uuid" in self.publisher.event_response_uuids

    def test_publish_event_subscribes_to_response_and_publishes(self):
        offer = Offer("1", now(), 2, 3, TraderDetails("A", ""))
        trade = Trade("2", now(), TraderDetails("B", ""), TraderDetails("C", ""),
                      offer=Offer("accepted", now(), 7, 8, TraderDetails("Z", "")),
                      traded_energy=1, trade_price=1)
        new_offer = Offer("3", now(), 4, 5, TraderDetails("D", ""))
        existing_offer = Offer("4", now(), 5, 6, TraderDetails("E", ""))
        kwargs = {"offer": offer,
                  "trade": trade,
                  "new_offer": new_offer,
                  "existing_offer": existing_offer}

        self.publisher.publish_event(MarketEvent.OFFER, **kwargs)
        self.publisher.redis.sub_to_channel.assert_called_once_with(
            "market/test_id/notify_event/response",
            self.publisher.response_callback
        )

        expected_result = {k: v.to_json_string() for k, v in kwargs.items()}
        self.publisher.redis.publish.assert_called_once()
        assert self.publisher.redis.publish.call_args_list[0][0][0] == \
            "market/test_id/notify_event"
        publish_call_args = json.loads(self.publisher.redis.publish.call_args_list[0][0][1])
        assert publish_call_args["event_type"] == MarketEvent.OFFER.value
        assert len(DeepDiff(publish_call_args["kwargs"], expected_result)) == 0

    def test_wait_for_event_response_calls_poll_method(self):
        self.publisher.event_response_uuids = ["test_uuid"]
        self.publisher._wait_for_event_response({"transaction_uuid": "test_uuid"})
        self.publisher.redis.poll_until_response_received.assert_called()
        assert "test_uuid" not in self.publisher.event_response_uuids


class TestMarketRedisEventSubscriber(unittest.TestCase):

    def setUp(self):
        self.market = OneSidedMarket(name="test_market", time_slot=test_datetime)
        self.market.id = "id"
        self.subscriber = MarketRedisEventSubscriber(self.market)

    def tearDown(self):
        pass

    def test_subscribes_to_market_channels(self):
        self.subscriber.redis_db.sub_to_multiple_channels.assert_called_once_with(
            {
                "id/OFFER": self.subscriber._offer,
                "id/DELETE_OFFER": self.subscriber._delete_offer,
                "id/ACCEPT_OFFER": self.subscriber._accept_offer
            }
        )

    def test_stop_terminates_futures_and_redis_connection(self):

        self.subscriber.futures = [
            MagicMock(autospec=Future), MagicMock(autospec=Future),
            MagicMock(autospec=Future), MagicMock(autospec=Future)]
        self.subscriber.stop()
        assert self.subscriber.futures == []
        self.subscriber.redis_db.terminate_connection.assert_called_once()

    def test_parse_order_objects(self):
        input_data = {
            "trade_bid_info": {
                "original_bid_rate": 20, "propagated_bid_rate": 30,
                "original_offer_rate": 99, "propagated_offer_rate": 10,
                "trade_rate": 12},
            "offer_or_id": json.dumps({
                "id": "offer_id2", "type": "Offer",
                "price": 123, "energy": 4321, "seller": {"name": "offer_seller2", "uuid": ""}}),
            "offer": json.dumps({
                "id": "offer_id", "type": "Offer",
                "price": 654, "energy": 765, "seller": {"name": "offer_seller", "uuid": ""}}),
        }
        output_data = self.subscriber._parse_order_objects(input_data)
        assert isinstance(output_data["offer"], Offer)
        assert isinstance(output_data["offer_or_id"], Offer)
        assert isinstance(output_data["trade_bid_info"], dict)

        assert output_data["trade_bid_info"]["original_bid_rate"] == 20
        assert output_data["trade_bid_info"]["propagated_bid_rate"] == 30
        assert output_data["trade_bid_info"]["original_offer_rate"] == 99
        assert output_data["trade_bid_info"]["propagated_offer_rate"] == 10
        assert output_data["trade_bid_info"]["trade_rate"] == 12
        assert output_data["offer"].id == "offer_id"
        assert output_data["offer"].price == 654
        assert output_data["offer"].energy == 765
        assert output_data["offer"].seller.name == "offer_seller"
        assert output_data["offer_or_id"].id == "offer_id2"
        assert output_data["offer_or_id"].price == 123
        assert output_data["offer_or_id"].energy == 4321
        assert output_data["offer_or_id"].seller.name == "offer_seller2"

    def test_accept_offer_calls_market_method_and_publishes_response(self):
        offer = Offer("o_id", test_datetime, 12, 13, TraderDetails("o_seller", ""),
                      time_slot=test_datetime)
        payload = {"data": json.dumps({
                "buyer": TraderDetails("mykonos", "").serializable_dict(),
                "energy": 12,
                "offer_or_id": offer.to_json_string(),
                "transaction_uuid": "trans_id"
            })
        }
        trade = Trade(id="trade_id", creation_time=now(), offer=offer,
                      seller=TraderDetails("trade_seller", ""),
                      buyer=TraderDetails("trade_buyer", ""),
                      traded_energy=1, trade_price=1)
        self.market.accept_offer = MagicMock(return_value=trade)
        self.subscriber._accept_offer(payload)
        wait(self.subscriber.futures)
        self.subscriber.market.accept_offer.assert_called_once_with(
            buyer=TraderDetails("mykonos", "").serializable_dict(), energy=12, offer_or_id=offer)

        self.subscriber.redis_db.publish.assert_called_once_with(
            "id/ACCEPT_OFFER/RESPONSE", json.dumps({
                "status": "ready", "trade": trade.to_json_string(), "transaction_uuid": "trans_id"
            })
        )

    def test_offer_calls_market_method_and_publishes_response(self):

        payload = {"data": json.dumps({
                "seller": TraderDetails("mykonos", "").serializable_dict(),
                "energy": 12,
                "price": 32,
                "transaction_uuid": "trans_id"
            })
        }
        offer = Offer("o_id", now(), 32, 12, TraderDetails("o_seller", ""))
        self.market.offer = MagicMock(return_value=offer)
        self.subscriber._offer(payload)
        wait(self.subscriber.futures)
        self.subscriber.market.offer.assert_called_once_with(
            seller=TraderDetails("mykonos", "").serializable_dict(), energy=12, price=32
        )
        self.subscriber.redis_db.publish.assert_called_once_with(
            "id/OFFER/RESPONSE", json.dumps({
                "status": "ready", "offer": offer.to_json_string(), "transaction_uuid": "trans_id"
            })
        )

    def test_delete_offer_calls_market_method_and_publishes_response(self):
        offer = Offer("o_id", test_datetime, 32, 12, TraderDetails("o_seller", ""),
                      time_slot=test_datetime)
        payload = {"data": json.dumps({
                "offer_or_id": offer.to_json_string(),
                "transaction_uuid": "trans_id"
            })
        }

        self.market.delete_offer = MagicMock(return_value=offer)
        self.subscriber._delete_offer(payload)
        wait(self.subscriber.futures)
        self.subscriber.market.delete_offer.assert_called_once_with(offer_or_id=offer)
        self.subscriber.redis_db.publish.assert_called_once_with(
            "id/DELETE_OFFER/RESPONSE",
            json.dumps({"status": "ready", "transaction_uuid": "trans_id"})
        )


class TestTwoSidedMarketRedisEventSubscriber(unittest.TestCase):

    def setUp(self):
        ConstSettings.MASettings.MARKET_TYPE = 2
        self.market = OneSidedMarket(name="test_market", time_slot=now())
        self.market.id = "id"
        self.subscriber = TwoSidedMarketRedisEventSubscriber(self.market)

    def tearDown(self):
        ConstSettings.MASettings.MARKET_TYPE = 1

    def test_subscribes_to_market_channels(self):
        self.subscriber.redis_db.sub_to_multiple_channels.assert_called_once_with(
            {
                "id/OFFER": self.subscriber._offer,
                "id/DELETE_OFFER": self.subscriber._delete_offer,
                "id/ACCEPT_OFFER": self.subscriber._accept_offer,
                "id/DELETE_BID": self.subscriber._delete_bid,
                "id/ACCEPT_BID": self.subscriber._accept_bid,
                "id/BID": self.subscriber._bid,
            }
        )

    def test_accept_bid_calls_market_method_and_publishes_response(self):
        bid = Bid("b_id", now(), 12, 13, TraderDetails("b_buyer", ""))
        payload = {"data": json.dumps({
                "seller": TraderDetails("mykonos", "").serializable_dict(),
                "energy": 12,
                "bid": bid.to_json_string(),
                "transaction_uuid": "trans_id"
            })
        }
        trade = Trade(id="trade_id", creation_time=now(), bid=bid,
                      seller=TraderDetails("trade_seller", ""),
                      buyer=TraderDetails("trade_buyer", ""),
                      traded_energy=1, trade_price=1)
        self.market.accept_bid = MagicMock(return_value=trade)
        self.subscriber._accept_bid(payload)
        wait(self.subscriber.futures)
        self.subscriber.market.accept_bid.assert_called_once()
        self.subscriber.redis_db.publish.assert_called_once_with(
            "id/ACCEPT_BID/RESPONSE", json.dumps({
                "status": "ready", "trade": trade.to_json_string(),
                "transaction_uuid": "trans_id"
            })
        )

    def test_bid_calls_market_method_and_publishes_response(self):
        payload = {"data": json.dumps({
                "buyer": TraderDetails("mykonos", "").serializable_dict(),
                "energy": 12,
                "price": 32,
                "transaction_uuid": "trans_id"
            })
        }
        bid = Bid("b_id", now(), 32, 12, TraderDetails("b_buyer", ""))
        self.market.bid = MagicMock(return_value=bid)
        self.subscriber._bid(payload)
        wait(self.subscriber.futures)
        self.subscriber.market.bid.assert_called_once_with(
            buyer=TraderDetails("mykonos", "").serializable_dict(), energy=12, price=32
        )
        self.subscriber.redis_db.publish.assert_called_once_with(
            "id/BID/RESPONSE", json.dumps({
                "status": "ready", "bid": bid.to_json_string(), "transaction_uuid": "trans_id"
            })
        )

    def test_delete_bid_calls_market_method_and_publishes_response(self):
        bid = Bid("b_id", now(), 32, 12, TraderDetails("b_buyer", ""))
        payload = {"data": json.dumps({
                "bid": bid.to_json_string(),
                "transaction_uuid": "trans_id"
            })
        }

        self.market.delete_bid = MagicMock(return_value=bid)
        self.subscriber._delete_bid(payload)
        wait(self.subscriber.futures)
        self.subscriber.market.delete_bid.assert_called_once()
        self.subscriber.redis_db.publish.assert_called_once_with(
            "id/DELETE_BID/RESPONSE",
            json.dumps({"status": "ready", "transaction_uuid": "trans_id"})
        )
