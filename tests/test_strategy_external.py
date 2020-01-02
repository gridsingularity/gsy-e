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
            }
        )

    def test_sub_to_external_requests_exposes_correct_channels_one_sided_market(self):
        self.external_redis.redis_db.sub_to_multiple_channels.assert_called_once_with(
            {
                "parent-area/test-area/offer": self.external_redis._offer,
                "parent-area/test-area/delete_offer": self.external_redis._delete_offer,
                "parent-area/test-area/accept_offer": self.external_redis._accept_offer,
                "parent-area/test-area/offers": self.external_redis._offer_lists,
            }
        )

    def _assert_dict_is_the_same_as_offer(self, offer_dict, offer):
        assert offer.id == offer_dict["id"]
        assert offer.real_id == offer_dict["real_id"]
        assert offer.price == offer_dict["price"]
        assert offer.energy == offer_dict["energy"]
        assert offer.seller == offer_dict["seller"]

    def test_list_offers(self):
        offer1 = self.test_market.offer(1, 2, "A")
        offer2 = self.test_market.offer(2, 3, "B")
        offer3 = self.test_market.offer(3, 4, "C")
        self.external_redis._offer_lists("")
        self.external_redis.redis_db.publish.assert_called_once()
        assert self.external_redis.redis_db.publish.call_args_list[0][0][0] == \
            "parent-area/test-area/offers/response"
        response_payload = json.loads(
            self.external_redis.redis_db.publish.call_args_list[0][0][1])
        offers_dict = json.loads(response_payload["offer_list"])
        assert len(offers_dict.keys()) == 3
        self._assert_dict_is_the_same_as_offer(json.loads(offers_dict[offer1.id]), offer1)
        self._assert_dict_is_the_same_as_offer(json.loads(offers_dict[offer2.id]), offer2)
        self._assert_dict_is_the_same_as_offer(json.loads(offers_dict[offer3.id]), offer3)

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
        offer1 = self.test_market.offer(1, 2, "A")
        payload = {"data": json.dumps({"offer": offer1.id})}
        self.external_redis._delete_offer(payload)
        assert len(self.test_market.offers) == 0
        self.external_redis.redis_db.publish.assert_called_once()
        assert self.external_redis.redis_db.publish.call_args_list[0][0][0] == \
            "parent-area/test-area/delete_offer/response"

    def test_accept_offer(self):
        offer1 = self.test_market.offer(1, 2, "A")
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
        payload = {"data": json.dumps({"energy": 12, "price": 32})}
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
        bid1 = self.test_market.bid(1, 2, "B", "C")
        payload = {"data": json.dumps({"bid": bid1.id})}
        self.external_redis._delete_bid(payload)
        assert len(self.test_market.bids) == 0
        self.external_redis.redis_db.publish.assert_called_once()
        assert self.external_redis.redis_db.publish.call_args_list[0][0][0] == \
            "parent-area/test-area/delete_bid/response"
