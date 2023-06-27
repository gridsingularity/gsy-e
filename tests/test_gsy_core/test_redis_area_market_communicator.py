# pylint: disable=redefined-outer-name
from unittest.mock import patch, Mock

import pytest
from redis import Redis
from gsy_framework.redis_channels import AggregatorChannels


from gsy_e.gsy_e_core.redis_connections.aggregator import AggregatorHandler
from gsy_e.gsy_e_core.redis_connections.area_market import ExternalConnectionCommunicator


@pytest.fixture(scope="function", autouse=True)
def fixture_strict_redis():
    with patch("gsy_e.gsy_e_core.redis_connections.area_market.Redis",
               spec=Redis):

        yield


@pytest.fixture(scope="function", autouse=True)
def fixture_aggregator_handler():
    with patch(
            "gsy_e.gsy_e_core.redis_connections.area_market.AggregatorHandler",
            spec=AggregatorHandler):
        yield


@pytest.fixture(scope="function", name="enabled_communicator")
def fixture_enabled_communicator():
    return ExternalConnectionCommunicator(is_enabled=True)


@pytest.fixture(scope="function", name="disabled_communicator")
def fixture_disabled_communicator():
    return ExternalConnectionCommunicator(is_enabled=False)


class TestExternalConnectionCommunicator:

    @staticmethod
    def test_init(enabled_communicator, disabled_communicator):
        assert not disabled_communicator.is_enabled
        assert disabled_communicator.aggregator is None
        assert not hasattr(disabled_communicator, "redis_db")
        assert not hasattr(disabled_communicator, "channel_callback_dict")

        assert enabled_communicator.is_enabled
        assert enabled_communicator.aggregator is not None
        assert hasattr(enabled_communicator, "redis_db")
        assert hasattr(enabled_communicator, "channel_callback_dict")

    @staticmethod
    def test_sub_to_channel(enabled_communicator, disabled_communicator):
        callback = Mock()
        disabled_communicator.sub_to_channel(channel="channel", callback=callback)
        assert not hasattr(disabled_communicator, "pubsub")
        enabled_communicator.sub_to_channel(channel="channel", callback=callback)
        enabled_communicator.pubsub.subscribe.assert_called_once_with(**{"channel": callback})

    @staticmethod
    def test_sub_to_multiple_channels(enabled_communicator, disabled_communicator):
        callback = Mock()
        disabled_communicator.sub_to_multiple_channels({"channel": callback})
        assert not hasattr(disabled_communicator, "pubsub")
        enabled_communicator.sub_to_multiple_channels({"channel": callback})
        enabled_communicator.pubsub.subscribe.assert_called_once_with(**{"channel": callback})

    @staticmethod
    def test_start_communication(enabled_communicator, disabled_communicator):
        disabled_communicator.start_communication()
        assert not hasattr(disabled_communicator, "pubsub")
        enabled_communicator.pubsub.subscribed = False
        enabled_communicator.start_communication()
        enabled_communicator.pubsub.run_in_thread.assert_not_called()

        enabled_communicator.pubsub.subscribed = True
        enabled_communicator.start_communication()
        enabled_communicator.pubsub.run_in_thread.assert_called_once()

    @staticmethod
    def test_sub_to_aggregator(enabled_communicator, disabled_communicator):
        disabled_communicator.sub_to_aggregator()
        assert not hasattr(disabled_communicator, "pubsub")
        channel_names = AggregatorChannels()
        channel_callback_dict = {
            channel_names.batch_commands:
                enabled_communicator.aggregator.receive_batch_commands_callback,
            channel_names.commands: enabled_communicator.aggregator.aggregator_callback
        }

        enabled_communicator.sub_to_aggregator()
        enabled_communicator.pubsub.psubscribe.assert_called_once_with(
            **channel_callback_dict
        )

    @staticmethod
    def test_approve_aggregator_commands(enabled_communicator, disabled_communicator):
        disabled_communicator.approve_aggregator_commands()
        assert disabled_communicator.aggregator is None

        enabled_communicator.approve_aggregator_commands()
        enabled_communicator.aggregator.approve_batch_commands.assert_called_once()

    @staticmethod
    def test_publish_aggregator_commands_responses_events(
            enabled_communicator, disabled_communicator):
        disabled_communicator.publish_aggregator_commands_responses_events()
        assert disabled_communicator.aggregator is None

        enabled_communicator.publish_aggregator_commands_responses_events()
        enabled_communicator.aggregator.publish_all_commands_responses.assert_called_once()
        enabled_communicator.aggregator.publish_all_events.assert_called_once()
