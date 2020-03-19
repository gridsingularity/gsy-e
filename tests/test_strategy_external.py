import unittest
from unittest.mock import MagicMock
from parameterized import parameterized
import json
from d3a_interface.constants_limits import ConstSettings
from d3a.models.area import Area
from d3a.models.market.two_sided_pay_as_bid import TwoSidedPayAsBid
from d3a.models.strategy.external_strategy import ExternalStrategy
import d3a.models.market.market_redis_connection

d3a.models.market.market_redis_connection.BlockingCommunicator = MagicMock
d3a.models.market.market_redis_connection.ResettableCommunicator = MagicMock


class TestExternalStrategy(unittest.TestCase):

    def setUp(self):
        ConstSettings.IAASettings.MARKET_TYPE = 1
        self.area = Area(name="test_area")
        self.parent_area = Area(name="parent_area")
        self.test_market = TwoSidedPayAsBid(name="test_market")
        self.parent_area._markets.markets = {1: self.test_market}
        self.area.parent = self.parent_area
        self.external_strategy = ExternalStrategy(self.area)
        self.external_redis = self.external_strategy.redis

    def tearDown(self):
        ConstSettings.IAASettings.MARKET_TYPE = 1

    @parameterized.expand([(2, ), (3, )])
    def test_sub_to_external_requests_exposes_correct_channels_two_sided_market(self, market_type):
        ConstSettings.IAASettings.MARKET_TYPE = market_type
        self.external_strategy2 = ExternalStrategy(self.area)
        self.external_strategy2.redis.redis_db.sub_to_multiple_channels.assert_called_once_with(
            {
                "parent-area/test-area/offer": self.external_strategy2.redis._offer,
                "parent-area/test-area/delete_offer": self.external_strategy2.redis._delete_offer,
                "parent-area/test-area/delete_bid": self.external_strategy2.redis._delete_bid,
                "parent-area/test-area/bid": self.external_strategy2.redis._bid,
                "parent-area/test-area/bids": self.external_strategy2.redis._list_bids,
                "parent-area/test-area/offers": self.external_strategy2.redis._offer_lists
            }
        )

    def test_sub_to_external_requests_exposes_correct_channels_one_sided_market(self):
        self.external_redis.redis_db.sub_to_multiple_channels.assert_called_once_with(
            {
                "parent-area/test-area/offer": self.external_redis._offer,
                "parent-area/test-area/delete_offer": self.external_redis._delete_offer,
                "parent-area/test-area/accept_offer": self.external_redis._accept_offer,
                "parent-area/test-area/offers": self.external_redis._offer_lists
            }
        )

    def _assert_dict_is_the_same_as_offer(self, offer_dict, offer):
        assert offer.id == offer_dict["id"]
        assert offer.price == offer_dict["price"]
        assert offer.energy == offer_dict["energy"]

    def test_list_offers(self):
        offer1 = self.test_market.offer(1, 2, "A", "A")
        offer2 = self.test_market.offer(2, 3, "B", "B")
        offer3 = self.test_market.offer(3, 4, "C", "C")
        self.external_redis._offer_lists("")
        self.external_redis.redis_db.publish.assert_called_once()
        assert self.external_redis.redis_db.publish.call_args_list[0][0][0] == \
            "parent-area/test-area/offers/response"
        response_payload = json.loads(
            self.external_redis.redis_db.publish.call_args_list[0][0][1])
        offers_dict = response_payload["offer_list"]
        assert len(offers_dict) == 3
        self._assert_dict_is_the_same_as_offer(offers_dict[0], offer1)
        self._assert_dict_is_the_same_as_offer(offers_dict[1], offer2)
        self._assert_dict_is_the_same_as_offer(offers_dict[2], offer3)

    @parameterized.expand([(2, ), (3, )])
    def test_list_offers_two_sided(self, market_type):
        ConstSettings.IAASettings.MARKET_TYPE = market_type
        offer1 = self.test_market.offer(1, 2, "test_area", "test_area")
        offer2 = self.test_market.offer(2, 3, "test_area", "test_area")
        self.test_market.offer(3, 4, "C", "C")
        self.external_redis._offer_lists("")
        self.external_redis.redis_db.publish.assert_called_once()
        assert self.external_redis.redis_db.publish.call_args_list[0][0][0] == \
            "parent-area/test-area/offers/response"
        response_payload = json.loads(
            self.external_redis.redis_db.publish.call_args_list[0][0][1])
        offers_dict = response_payload["offer_list"]
        assert len(offers_dict) == 2
        self._assert_dict_is_the_same_as_offer(offers_dict[0], offer1)
        self._assert_dict_is_the_same_as_offer(offers_dict[1], offer2)

    def test_offer(self):
        payload = {"data": json.dumps({"energy": 22, "price": 54})}
        self.external_redis._offer(payload)
        assert len(self.test_market.offers) == 1
        offer = list(self.test_market.offers.values())[0]
        assert offer.price == 54
        assert offer.energy == 22
        assert offer.seller == "test_area"
        market_offer_json = offer.to_JSON_string()
        self.external_redis.redis_db.publish.assert_called_once()
        assert self.external_redis.redis_db.publish.call_args_list[0][0][0] == \
            "parent-area/test-area/offer/response"
        response_payload = json.loads(self.external_redis.redis_db.publish.call_args_list[0][0][1])
        assert response_payload["offer"] == market_offer_json

    def test_delete_offer(self):
        offer1 = self.test_market.offer(1, 2, "A", "A")
        payload = {"data": json.dumps({"offer": offer1.id})}
        self.external_redis._delete_offer(payload)
        assert len(self.test_market.offers) == 0
        self.external_redis.redis_db.publish.assert_called_once()
        assert self.external_redis.redis_db.publish.call_args_list[0][0][0] == \
            "parent-area/test-area/delete_offer/response"

    def test_accept_offer(self):
        offer1 = self.test_market.offer(1, 2, "A", "A")
        payload = {"data": json.dumps({"offer": offer1.id})}
        self.external_redis._accept_offer(payload)
        assert len(self.test_market.trades) == 1
        trade = self.test_market.trades[0]
        assert len(self.test_market.offers) == 0
        self.external_redis.redis_db.publish.assert_called_once()
        assert self.external_redis.redis_db.publish.call_args_list[0][0][0] == \
            "parent-area/test-area/accept_offer/response"
        response_payload = json.loads(self.external_redis.redis_db.publish.call_args_list[0][0][1])
        assert response_payload["trade"] == trade.to_JSON_string()

    def test_bid(self):
        payload = {"data": json.dumps({"energy": 12, "price": 32, "transaction_id": "some_id"})}
        self.external_redis._bid(payload)
        assert len(self.test_market.bids) == 1
        bid = list(self.test_market.bids.values())[0]
        assert bid.price == 32
        assert bid.energy == 12
        assert bid.buyer == "test_area"
        assert bid.seller == "parent_area"
        self.external_redis.redis_db.publish.assert_called_once()
        assert self.external_redis.redis_db.publish.call_args_list[0][0][0] == \
            "parent-area/test-area/bid/response"
        response_payload = json.loads(self.external_redis.redis_db.publish.call_args_list[0][0][1])
        assert response_payload["bid"] == bid.to_JSON_string()

    def test_delete_bid(self):
        bid1 = self.test_market.bid(1, 2, "B", "C", "B")
        payload = {"data": json.dumps({"bid": bid1.id})}
        self.external_redis._delete_bid(payload)
        assert len(self.test_market.bids) == 0
        self.external_redis.redis_db.publish.assert_called_once()
        assert self.external_redis.redis_db.publish.call_args_list[0][0][0] == \
            "parent-area/test-area/delete_bid/response"

    @parameterized.expand([(2, ), (3, )])
    def test_list_bids(self, market_type):
        ConstSettings.IAASettings.MARKET_TYPE = market_type
        bid1 = self.test_market.bid(1, 2, "test_area", "A", "test_area")
        bid2 = self.test_market.bid(2, 3, "test_area", "B", "test_area")
        bid3 = self.test_market.bid(3, 4, "test_area", "C", "test_area")
        self.external_redis._list_bids("")
        self.external_redis.redis_db.publish.assert_called_once()
        assert self.external_redis.redis_db.publish.call_args_list[0][0][0] == \
            "parent-area/test-area/bids/response"
        response_payload = json.loads(
            self.external_redis.redis_db.publish.call_args_list[0][0][1])
        bids_list = response_payload["bid_list"]
        assert len(bids_list) == 3
        self._assert_dict_is_the_same_as_offer(bids_list[0], bid1)
        self._assert_dict_is_the_same_as_offer(bids_list[1], bid2)
        self._assert_dict_is_the_same_as_offer(bids_list[2], bid3)

    def test_get_channel_list_fetches_correct_channel_names(self):
        channel_list = self.external_strategy.get_channel_list()
        assert set(channel_list["available_publish_channels"]) == {
            "parent-area/test-area/offer",
            "parent-area/test-area/delete_offer",
            "parent-area/test-area/accept_offer",
            "parent-area/test-area/offers"
        }
        assert set(channel_list["available_subscribe_channels"]) == {
            "parent-area/test-area/market_cycle"
        }
