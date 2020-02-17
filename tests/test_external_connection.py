import unittest
from unittest.mock import MagicMock
import json
import d3a.models.area.redis_external_connection
from d3a.models.area import Area
from d3a.models.area.redis_external_connection import RedisAreaExternalConnection


class TestExternalConnectionRedis(unittest.TestCase):

    def setUp(self):
        self.ext_strategy_mock = MagicMock
        self.ext_strategy_mock.get_channel_list = lambda s: {}
        d3a.models.area.redis_external_connection.ExternalStrategy = self.ext_strategy_mock
        d3a.models.area.redis_external_connection.StrictRedis = MagicMock()
        redis_db_object = MagicMock()
        redis_db_object.pubsub = MagicMock
        d3a.models.area.redis_external_connection.StrictRedis.from_url = \
            MagicMock(return_value=redis_db_object)
        self.area = Area(name="base_area")
        self.external_connection = RedisAreaExternalConnection(self.area)

    def tearDown(self):
        pass

    def add_external_connections_to_area(self):
        area_list = ["kreuzberg", "friedrichschain", "prenzlauer berg"]
        self.external_connection.areas_to_register = area_list
        self.external_connection.register_new_areas()
        return area_list

    def test_external_connection_subscribes_to_register_unregister(self):
        self.external_connection.pubsub.subscribe.assert_called_once_with(
            **{
                "base-area/register_participant":
                    self.external_connection.channel_register_callback,
                "base-area/unregister_participant":
                    self.external_connection.channel_unregister_callback,
                "base-area/market_stats":
                    self.external_connection.market_stats_callback,
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
        area_list = self.add_external_connections_to_area()
        assert len(self.area.children) == 3
        assert not self.external_connection.areas_to_register
        assert set(ch.name for ch in self.area.children) == set(area_list)
        assert all(isinstance(ch.strategy, self.ext_strategy_mock) for ch in self.area.children)
        assert all(ch.parent == self.area for ch in self.area.children)
        assert all(ch.active for ch in self.area.children)
        assert self.external_connection.redis_db.publish.call_count == 3
        for i, created_area in enumerate(area_list):
            assert self.external_connection.redis_db.publish.call_args_list[i][0][0] == \
                "base-area/register_participant/response"

    def test_unregister_areas_deletes_children_from_area(self):
        area_list = self.add_external_connections_to_area()
        assert set(ch.name for ch in self.area.children) == set(area_list)
        # Keep track how many times the publish method was called when setting up the areas
        call_count = self.external_connection.redis_db.publish.call_count
        # Monkeypatch shutdown method of ExternalStrategy class
        for ch in self.area.children:
            ch.strategy.shutdown = MagicMock()

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
        area_list = self.add_external_connections_to_area()
        assert set(ch.name for ch in self.area.children) == set(area_list)

        self.external_connection.areas_to_unregister = ["schoneberg"]
        self.external_connection.unregister_pending_areas()
        assert len(self.area.children) == 3
        self.external_connection.redis_db.publish.assert_called_with(
            "base-area/unregister_participant/response", json.dumps({"response": "failed"}))
