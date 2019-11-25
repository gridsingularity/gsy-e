import unittest
from unittest.mock import MagicMock
import json
from slugify import slugify
import d3a.models.area.redis_external_connection
from d3a.models.area import Area
from d3a.models.area.redis_external_connection import RedisExternalConnection
from d3a.models.strategy.external_strategy import ExternalStrategy


class TestExternalConnectionRedis(unittest.TestCase):

    def setUp(self):
        d3a.models.area.redis_external_connection.StrictRedis = MagicMock()
        redis_db_object = MagicMock()
        redis_db_object.pubsub = MagicMock
        d3a.models.area.redis_external_connection.StrictRedis.from_url = \
            MagicMock(return_value=redis_db_object)
        self.area = Area(name="base_area")
        self.external_connection = RedisExternalConnection(self.area)

    def tearDown(self):
        pass

    def test_external_connection_subscribes_to_register_unregister(self):
        self.external_connection.pubsub.subscribe.assert_called_once_with(
            **{
                "base-area/register_participant":
                    self.external_connection.channel_register_callback,
                "base-area/unregister_participant":
                    self.external_connection.channel_unregister_callback
            }
        )

    def test_register_message_adds_area_to_buffer(self):
        self.external_connection.channel_register_callback(
            {"data": json.dumps({"name": "berlin"})}
        )
        assert self.external_connection.areas_to_register == ["berlin"]

    def test_unregister_message_adds_area_to_buffer(self):
        self.external_connection.channel_unregister_callback(
            {"data": json.dumps({"name": "berlin"})}
        )
        assert self.external_connection.areas_to_unregister == ["berlin"]

    def test_register_new_areas_creates_new_child_areas_from_buffer(self):
        area_list = ["kreuzberg", "friedrichschain", "prenzlauer berg"]
        self.external_connection.areas_to_register = area_list
        self.external_connection.register_new_areas()
        assert len(self.area.children) == 3
        assert not self.external_connection.areas_to_register
        assert set(ch.name for ch in self.area.children) == set(area_list)
        assert all(isinstance(ch.strategy, ExternalStrategy) for ch in self.area.children)
        assert all(ch.parent == self.area for ch in self.area.children)
        assert all(ch.active for ch in self.area.children)
        assert self.external_connection.redis_db.publish.call_count == 3
        for i, created_area in enumerate(area_list):
            assert self.external_connection.redis_db.publish.call_args_list[i][0][0] == \
                "base-area/register_participant/response"
            assert self.external_connection.redis_db.publish.call_args_list[i][0][1] == \
                json.dumps({"available_publish_channels": [
                   f"base-area/{slugify(created_area)}/offer",
                   f"base-area/{slugify(created_area)}/offer_delete",
                   f"base-area/{slugify(created_area)}/offer_accept"
                ], "available_subscribe_channels": [
                   f"base-area/{slugify(created_area)}/offers",
                   f"base-area/{slugify(created_area)}/offer/response",
                   f"base-area/{slugify(created_area)}/offer_delete/response",
                   f"base-area/{slugify(created_area)}/offer_accept/response"
                ]})

    def test_unregister_areas_deletes_children_from_area(self):
        area_list = ["kreuzberg", "friedrichschain", "prenzlauer berg"]
        self.external_connection.areas_to_register = area_list
        self.external_connection.register_new_areas()
        assert set(ch.name for ch in self.area.children) == set(area_list)
        # Keep track how many times the publish method was called when setting up the areas
        call_count = self.external_connection.redis_db.publish.call_count

        self.external_connection.areas_to_unregister = ["prenzlauer berg"]
        self.external_connection.unregister_pending_areas()
        assert len(self.area.children) == 2
        assert self.external_connection.redis_db.publish.call_count == call_count + 1
        self.external_connection.redis_db.publish.assert_called_with(
            "base-area/unregister_participant/response", json.dumps({"response": "success"}))

        self.external_connection.areas_to_unregister = ["friedrichschain"]
        self.external_connection.unregister_pending_areas()
        assert len(self.area.children) == 1
        assert self.external_connection.redis_db.publish.call_count == call_count + 2
        self.external_connection.redis_db.publish.assert_called_with(
            "base-area/unregister_participant/response", json.dumps({"response": "success"}))

    def test_unregister_area_that_does_not_exist_returns_an_error(self):
        area_list = ["kreuzberg", "friedrichschain", "prenzlauer berg"]
        self.external_connection.areas_to_register = area_list
        self.external_connection.register_new_areas()
        assert set(ch.name for ch in self.area.children) == set(area_list)

        self.external_connection.areas_to_unregister = ["schoneberg"]
        self.external_connection.unregister_pending_areas()
        assert len(self.area.children) == 3
        self.external_connection.redis_db.publish.assert_called_with(
            "base-area/unregister_participant/response", json.dumps({"response": "failed"}))

    def test_subscribe_channel_list_fetches_correct_channel_names(self):
        channel_list = json.loads(self.external_connection._subscribe_channel_list("test-area"))
        assert set(channel_list["available_publish_channels"]) == {
            "base-area/test-area/offer",
            "base-area/test-area/offer_delete",
            "base-area/test-area/offer_accept"
        }
        assert set(channel_list["available_subscribe_channels"]) == {
            "base-area/test-area/offers",
            "base-area/test-area/offer/response",
            "base-area/test-area/offer_delete/response",
            "base-area/test-area/offer_accept/response"
        }
