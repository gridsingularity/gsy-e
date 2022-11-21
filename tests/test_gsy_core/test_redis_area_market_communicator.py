from unittest.mock import patch, Mock

import pytest
from redis import Redis

from gsy_e.gsy_e_core.redis_connections.aggregator import AggregatorHandler
from gsy_e.gsy_e_core.redis_connections.area_market import ExternalConnectionCommunicator


@pytest.fixture(scope="function", autouse=True)
def strict_redis():
    with patch("gsy_e.gsy_e_core.redis_connections.area_market.Redis",
               spec=Redis):

        yield


@pytest.fixture(scope="function", autouse=True)
def aggregator_handler():
    with patch(
            "gsy_e.gsy_e_core.redis_connections.area_market.AggregatorHandler",
            spec=AggregatorHandler):
        yield


@pytest.fixture(scope="function")
def enabled_communicator(strict_redis):
    return ExternalConnectionCommunicator(is_enabled=True)


@pytest.fixture(scope="function")
def disabled_communicator(strict_redis):
    return ExternalConnectionCommunicator(is_enabled=False)


class TestExternalConnectionCommunicator:

    def test_init(self, enabled_communicator, disabled_communicator):
        assert not disabled_communicator.is_enabled
        assert disabled_communicator.aggregator is None
        assert not hasattr(disabled_communicator, "redis_db")
        assert not hasattr(disabled_communicator, "channel_callback_dict")

        assert enabled_communicator.is_enabled
        assert enabled_communicator.aggregator is not None
        assert hasattr(enabled_communicator, "redis_db")
        assert hasattr(enabled_communicator, "channel_callback_dict")

    def test_sub_to_channel(self, enabled_communicator, disabled_communicator):
        callback = Mock()
        disabled_communicator.sub_to_channel(channel="channel", callback=callback)
        assert not hasattr(disabled_communicator, "pubsub")
        enabled_communicator.sub_to_channel(channel="channel", callback=callback)
        enabled_communicator.pubsub.subscribe.assert_called_once_with(**{"channel": callback})

    def test_sub_to_multiple_channels(self, enabled_communicator, disabled_communicator):
        callback = Mock()
        disabled_communicator.sub_to_multiple_channels({"channel": callback})
        assert not hasattr(disabled_communicator, "pubsub")
        enabled_communicator.sub_to_multiple_channels({"channel": callback})
        enabled_communicator.pubsub.subscribe.assert_called_once_with(**{"channel": callback})

    def test_start_communication(self, enabled_communicator, disabled_communicator):
        disabled_communicator.start_communication()
        assert not hasattr(disabled_communicator, "pubsub")

        enabled_communicator.pubsub.run_in_thread.assert_called_once()

    def test_sub_to_aggregator(self, enabled_communicator, disabled_communicator):
        disabled_communicator.sub_to_aggregator()
        assert not hasattr(disabled_communicator, "pubsub")
        channel_callback_dict = {
            "external//aggregator/*/batch_commands":
                enabled_communicator.aggregator.receive_batch_commands_callback,
            "aggregator": enabled_communicator.aggregator.aggregator_callback
        }
        enabled_communicator.pubsub.psubscribe.assert_called_once_with(
            **channel_callback_dict
        )

    def test_approve_aggregator_commands(self, enabled_communicator, disabled_communicator):
        disabled_communicator.approve_aggregator_commands()
        assert disabled_communicator.aggregator is None

        enabled_communicator.approve_aggregator_commands()
        enabled_communicator.aggregator.approve_batch_commands.assert_called_once()

    def test_publish_aggregator_commands_responses_events(
            self, enabled_communicator, disabled_communicator):
        disabled_communicator.publish_aggregator_commands_responses_events()
        assert disabled_communicator.aggregator is None

        enabled_communicator.publish_aggregator_commands_responses_events()
        enabled_communicator.aggregator.publish_all_commands_responses.assert_called_once()
        enabled_communicator.aggregator.publish_all_events.assert_called_once()
