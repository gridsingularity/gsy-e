import json
from unittest.mock import Mock, patch, PropertyMock

import pytest
from gsy_framework.exceptions import GSyAreaException

from gsy_e.models.area.redis_external_market_connection import RedisMarketExternalConnection


# pylint:disable=protected-access, disable=no-self-use

@pytest.fixture(name="market_connection")
def redis_external_market_connection_fixture() -> "RedisMarketExternalConnection":
    """Return the redis_ext_conn member of the area"""
    area = Mock()
    return RedisMarketExternalConnection(area)


class TestRedisMarketExternalConnection:
    """Tester class for the RedisMarketExternalConnection."""

    def test_spot_market(self, market_connection):
        """Test whether the spot_market property is the same as the area's."""
        assert market_connection.spot_market == market_connection.area.spot_market

    def test_is_aggregator_controlled(self, market_connection):
        """Test the is_aggregator_controlled flag."""
        market_connection.aggregator = Mock()
        # aggregator member is defined and is_controlling_device returns True
        market_connection.aggregator.is_controlling_device = Mock(return_value=True)
        assert market_connection.is_aggregator_controlled

        # aggregator member is defined and is_controlling_device returns False
        market_connection.aggregator.is_controlling_device.return_value = False
        assert not market_connection.is_aggregator_controlled

        # aggregator member is not defined
        market_connection.aggregator.is_controlling_device.return_value = True
        market_connection.aggregator = None
        assert not market_connection.is_aggregator_controlled

    def test_get_transaction_id(self, market_connection):
        """Test the extraction of transaction_id from messages."""
        data = json.dumps({"transaction_id": "123"})
        assert market_connection._get_transaction_id({"data": data}) == "123"

        data = json.dumps({})
        with pytest.raises(ValueError):
            market_connection._get_transaction_id({"data": data})

    @patch("gsy_e.models.area.redis_external_market_connection."
           "ExternalStrategyConnectionManager.register")
    def test_register(self, register_mock, market_connection):
        """Test whether the register method correctly updates the _connected flag."""
        assert not market_connection._connected
        market_connection._get_transaction_id = Mock(return_value="mock_transaction_id")
        register_mock.return_value = True
        assert market_connection._register({}) is None
        assert market_connection._connected
        register_mock.assert_called_once_with(
            market_connection._redis_communicator,
            market_connection.channel_names.register_response,
            False, "mock_transaction_id", area_uuid=market_connection.area.uuid)

    @patch("gsy_e.models.area.redis_external_market_connection."
           "ExternalStrategyConnectionManager.unregister")
    def test_unregister(self, unregister_mock, market_connection):
        """Test whether the unregister method correctly updates the _connected flag."""
        market_connection._connected = True
        market_connection._get_transaction_id = Mock(return_value="mock_transaction_id")
        unregister_mock.return_value = False
        assert market_connection._unregister({}) is None
        assert not market_connection._connected
        unregister_mock.assert_called_once_with(
            market_connection._redis_communicator,
            market_connection.channel_names.unregister_response,
            True, "mock_transaction_id")

    def test_sub_to_external_channels(self, market_connection):
        """Test whether the instance is subscribing to all supported channels."""
        market_connection._redis_communicator = Mock()
        assert market_connection.aggregator is None
        market_connection._redis_communicator.is_enabled = False
        market_connection.sub_to_external_channels()
        assert market_connection.aggregator is not None
        market_connection._redis_communicator.sub_to_multiple_channels.assert_called_once_with({
            market_connection.channel_names.dso_market_stats:
                market_connection.dso_market_stats_callback,
            market_connection.channel_names.grid_fees:
                market_connection.set_grid_fees_callback,
            market_connection.channel_names.register:
                market_connection._register,
            market_connection.channel_names.unregister:
                market_connection._unregister
        })

        market_connection._redis_communicator.is_enabled = True
        market_connection.sub_to_external_channels()
        assert market_connection.aggregator is not None

    def test_set_grid_fees_callback_conflicting_grid_fee_type_config(self, market_connection):
        """Test the set_grid_fees callback by passing a conflicting grid fee type."""
        market_connection.area.area_reconfigure_event = Mock()
        market_connection._redis_communicator = Mock()

        # market_connection._connected is False -> should return early
        market_connection.set_grid_fees_callback({"data": {"fee_percent": 12}})
        market_connection.area.area_reconfigure_event.assert_not_called()

        # market_connection._connected is True
        # passing fee_percent while config.grid_fee_type != 2
        market_connection._connected = True
        expected_response = {"area_uuid": market_connection.area.uuid,
                             "command": "grid_fees", "status": "error", "error_message":
                                 "GridFee parameter conflicting with GlobalConfigFeeType",
                             "transaction_id": None}
        assert market_connection.set_grid_fees_callback({"data": {"fee_percent": 12}}) is None
        market_connection.area.area_reconfigure_event.assert_not_called()
        market_connection._redis_communicator.publish_json.assert_called_once_with(
            market_connection.channel_names.grid_fees_response, expected_response)

        # In the case of is_aggregator_controlled = True, the callback should return the response
        with patch("gsy_e.models.area.redis_external_market_connection."
                   "RedisMarketExternalConnection.is_aggregator_controlled", True):
            expected_response.pop("transaction_id")
            assert market_connection.set_grid_fees_callback(
                {"data": {"fee_percent": 12}}) == expected_response

    def test_set_grid_fees_callback_valid_grid_fee_type_config(self, market_connection):
        """Test the set_grid_fees callback by passing a valid grid fee type."""
        market_connection._connected = True
        market_connection.area.area_reconfigure_event = Mock()
        market_connection._redis_communicator = Mock()

        # passing fee_percent while config.grid_fee_type == 2
        market_connection.area.grid_fee_constant = None
        grid_fee_percentage = 12
        market_connection.area.grid_fee_percentage = grid_fee_percentage
        market_connection.area.config.grid_fee_type = 2

        expected_response = {"area_uuid": market_connection.area.uuid,
                             "command": "grid_fees", "status": "ready", "market_fee_const":
                                 "None", "market_fee_percent": str(grid_fee_percentage),
                             "transaction_id": None}
        assert market_connection.set_grid_fees_callback(
            {"data": {"fee_percent": grid_fee_percentage}}) is None
        market_connection.area.area_reconfigure_event.assert_called_once_with(
            grid_fee_percentage=grid_fee_percentage, grid_fee_constant=None)
        market_connection._redis_communicator.publish_json.assert_called_once_with(
            market_connection.channel_names.grid_fees_response, expected_response)

        # In the case of is_aggregator_controlled = True, the callback should return the response
        with patch("gsy_e.models.area.redis_external_market_connection."
                   "RedisMarketExternalConnection.is_aggregator_controlled", True):
            expected_response.pop("transaction_id")
            assert market_connection.set_grid_fees_callback(
                {"data": {"fee_percent": grid_fee_percentage}}) == expected_response

    def test_set_grid_fees_callback_gsy_e_exception(self, market_connection):
        """Test the set_grid_fees callback when the area_reconfigure_event raises an exception."""
        market_connection._connected = True
        market_connection.area.area_reconfigure_event = Mock()
        market_connection._redis_communicator = Mock()
        market_connection.area.area_reconfigure_event.side_effect = GSyAreaException
        market_connection.set_grid_fees_callback({"data": {"fee_percent": 12}})
        market_connection._redis_communicator.assert_not_called()

    def test_dso_market_stats_callback(self, market_connection):
        """Test the dso_market_stats_callback method."""
        response_channel = market_connection.channel_names.dso_market_stats_response
        market_connection._redis_communicator = Mock()
        assert market_connection.dso_market_stats_callback({"data": {}}) is None
        market_connection._redis_communicator.assert_not_called()

        market_connection._connected = True
        response = {"status": "ready",
                    "name": market_connection.area.name,
                    "area_uuid": market_connection.area.uuid,
                    "command": "dso_market_stats",
                    "transaction_id": None,
                    "market_stats": market_connection.area.stats.get_last_market_stats(dso=True)}
        market_connection.dso_market_stats_callback({"data": {}})
        market_connection._redis_communicator.publish_json.assert_called_once_with(
            response_channel, response)

    @patch("gsy_e.models.area.redis_external_market_connection.RedisMarketExternalConnection."
           "_progress_info", {})
    def test_publish_market_cycle(self, market_connection):
        """Test the publish_market_cycle method."""
        market_connection.aggregator = Mock()
        type(market_connection.area).current_market = PropertyMock(return_value=None)
        market_connection.publish_market_cycle()

        market_connection.aggregator.add_batch_market_event.assert_not_called()

        type(market_connection.area).current_market = PropertyMock(return_value=True)
        market_connection.publish_market_cycle()
        market_connection.aggregator.add_batch_market_event.assert_called_once_with(
            market_connection.area.uuid, {})

    def test_deactivate(self, market_connection):
        """Test whether the deactivate method correctly dispatch the event."""
        market_connection.aggregator = Mock()
        market_connection._redis_communicator = Mock()
        # Dispatch to aggregator
        with patch("gsy_e.models.area.redis_external_market_connection."
                   "RedisMarketExternalConnection.is_aggregator_controlled", True):
            market_connection.deactivate()
        market_connection.aggregator.add_batch_finished_event.assert_called_once_with(
            market_connection.area.uuid, {"event": "finish"})
        market_connection._redis_communicator.publish_json.assert_not_called()

        # Dispatch to redis communicator
        market_connection.aggregator.reset_mock()
        market_connection._redis_communicator.is_enabled = True
        with patch("gsy_e.models.area.redis_external_market_connection."
                   "RedisMarketExternalConnection.is_aggregator_controlled", False):
            market_connection.deactivate()
        market_connection._redis_communicator.publish_json.assert_called_once_with(
            market_connection.channel_names.finish, {"event": "finish"})

    def test_trigger_aggregator_commands(self, market_connection):
        """Test how trigger_aggregator_commands calls the callbacks."""
        command = {}
        assert market_connection.trigger_aggregator_commands(command) == (
            {"status": "error",
             "area_uuid": market_connection.area.uuid,
             "message": "Invalid command type"}
        )

        command = {"type": "unsupported_command"}
        assert market_connection.trigger_aggregator_commands(command) == (
            {"command": command["type"], "status": "error",
             "area_uuid": market_connection.area.uuid,
             "message": f"Command type not supported for device {market_connection.area.uuid}"}
        )

        market_connection.set_grid_fees_callback = Mock()
        market_connection.set_grid_fees_callback.return_value = {"random": "value"}
        command = {"type": "grid_fees"}
        assert market_connection.trigger_aggregator_commands(command) == {"random": "value"}
