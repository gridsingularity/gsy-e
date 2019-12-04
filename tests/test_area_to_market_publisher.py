import unittest
from unittest.mock import MagicMock
import json
from d3a_interface.constants_limits import ConstSettings
from d3a.d3a_core.exceptions import D3ARedisException
from d3a.models.market.one_sided import OneSidedMarket
from d3a.models.area import Area
import d3a.models.area.redis_dispatcher.area_to_market_publisher
from d3a.models.area.redis_dispatcher.area_to_market_publisher import \
    AreaToMarketEventPublisher

d3a.models.area.redis_dispatcher.area_to_market_publisher.BlockingCommunicator = MagicMock


class TestAreaToMarketPublisher(unittest.TestCase):
    def setUp(self):
        ConstSettings.IAASettings.MARKET_TYPE = 2
        self.market1 = OneSidedMarket(name="test_market")
        self.market1.id = "id1"
        self.market2 = OneSidedMarket(name="test_market")
        self.market2.id = "id2"
        self.area = Area(name="test_area")
        self.area._markets.markets = {1: self.market1, 2: self.market2}
        self.publisher = AreaToMarketEventPublisher(self.area)

    def tearDown(self):
        ConstSettings.IAASettings.MARKET_TYPE = 1

    def test_area_to_market_event_response(self):
        self.publisher.response_callback({
            "data": json.dumps({"status": "ready", "transaction_uuid": "transaction1"})
        })
        assert "transaction1" in self.publisher.event_response_uuids

    def test_area_to_market_event_response_raises_error_for_incorrect_response(self):
        with self.assertRaises(D3ARedisException):
            self.publisher.response_callback({
                "data": json.dumps({"status": "ready"})
            })
        with self.assertRaises(D3ARedisException):
            self.publisher.response_callback({
                "data": json.dumps({"status": "failed", "transaction_uuid": "trans_id"})
            })

    def test_publish_market_clearing_subscribes_to_correct_channel_per_market(self):
        self.publisher.publish_markets_clearing()
        assert self.publisher.redis.sub_to_channel.call_count == 2
        called_arguments = self.publisher.redis.sub_to_channel.call_args_list
        assert called_arguments[0][0][0] == "id1/CLEAR/RESPONSE"
        assert called_arguments[0][0][1] == self.publisher.response_callback
        assert called_arguments[1][0][0] == "id2/CLEAR/RESPONSE"
        assert called_arguments[1][0][1] == self.publisher.response_callback

    def test_publish_market_clearing_publishes_to_correct_channel(self):
        self.publisher.publish_markets_clearing()
        assert self.publisher.redis.publish.call_count == 2
        assert self.publisher.redis.publish.call_args_list[0][0][0] == "id1/CLEAR"
        send_data = json.loads(self.publisher.redis.publish.call_args_list[0][0][1])
        assert "transaction_uuid" in send_data
        assert self.publisher.redis.publish.call_args_list[1][0][0] == "id2/CLEAR"
        send_data = json.loads(self.publisher.redis.publish.call_args_list[1][0][1])
        assert "transaction_uuid" in send_data

    def test_publish_market_clearing_waits_until_response_received(self):
        self.publisher.publish_markets_clearing()
        assert self.publisher.redis.poll_until_response_received.call_count == 2
