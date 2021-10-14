from unittest.mock import patch, MagicMock

import pytest
from redis import StrictRedis

from d3a.d3a_core.redis_connections.aggregator_connection import AggregatorHandler
from d3a.d3a_core.redis_connections.redis_area_market_communicator import (
    ExternalConnectionCommunicator)


@pytest.fixture(scope="function", autouse=True)
def strict_redis():
    patcher = patch("d3a.d3a_core.redis_connections.redis_area_market_communicator.StrictRedis",
                    spec=StrictRedis)
    patcher.start()
    yield
    patcher.stop()


@pytest.fixture(scope="function", autouse=True)
def aggregator_handler():
    patcher = patch(
        "d3a.d3a_core.redis_connections.redis_area_market_communicator.AggregatorHandler",
        spec=AggregatorHandler)
    patcher.start()
    yield
    patcher.stop()


class TestExternalConnectionCommunicator:

    def test_init(self):
        communicator = ExternalConnectionCommunicator(is_enabled=False)
        assert communicator.is_enabled is False
        assert communicator.aggregator is None
        assert hasattr(communicator, "redis_db") is False
        assert hasattr(communicator, "channel_callback_dict") is False

        communicator = ExternalConnectionCommunicator(is_enabled=True)
        assert communicator.is_enabled is True
        assert communicator.aggregator is not None
        assert hasattr(communicator, "redis_db") is True
        assert hasattr(communicator, "channel_callback_dict") is True

    def test_sub_to_channel(self):
        callback = lambda x: x
        communicator = ExternalConnectionCommunicator(is_enabled=True)
        communicator.sub_to_channel(channel="channel", callback=callback)
        communicator.pubsub.subscribe.assert_called_once_with(**{"channel": callback})

    def test_sub_to_multiple_channels(self):
        callback = lambda x: x
        communicator = ExternalConnectionCommunicator(is_enabled=True)
        communicator.sub_to_multiple_channels({"channel": callback})
        communicator.pubsub.subscribe.assert_called_once_with(**{"channel": callback})

    def test_start_communication(self):
        communicator = ExternalConnectionCommunicator(is_enabled=True)
        communicator.pubsub.subscribed = False
        communicator.start_communication()
        assert communicator.pubsub.run_in_thread.called is False

        communicator.pubsub.subscribed = True
        communicator.start_communication()
        assert communicator.pubsub.run_in_thread.called is True

    def test_sub_to_aggregator(self):
        communicator = ExternalConnectionCommunicator(is_enabled=True)
        communicator.sub_to_aggregator()
        communicator.pubsub.psubscribe.assert_called_once()

    def test_approve_aggregator_commands(self):
        communicator = ExternalConnectionCommunicator(is_enabled=True)
        communicator.approve_aggregator_commands()
        communicator.aggregator.approve_batch_commands.assert_called_once()

    def test_publish_aggregator_commands_responses_events(self):
        communicator = ExternalConnectionCommunicator(is_enabled=True)
        communicator.publish_aggregator_commands_responses_events()
        communicator.aggregator.publish_all_commands_responses.assert_called_once()
        communicator.aggregator.publish_all_events.assert_called_once()
