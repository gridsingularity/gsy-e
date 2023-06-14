"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import json
from logging import getLogger
from typing import Dict, Optional, TYPE_CHECKING

from gsy_framework.exceptions import GSyAreaException
from gsy_framework.redis_channels import ExternalStrategyChannels

import gsy_e
from gsy_e.models.strategy.external_strategies import (
    CommandTypeNotSupported, ExternalStrategyConnectionManager)

log = getLogger(__name__)

if TYPE_CHECKING:
    from gsy_e.models.area import Area
    from gsy_e.models.market import Market
    from gsy_e.gsy_e_core.redis_connections.aggregator import AggregatorHandler
    from gsy_e.gsy_e_core.redis_connections.area_market import ExternalConnectionCommunicator


class RedisMarketExternalConnection:
    """Enable external connection in the market areas (areas with no strategy).

    Although that the direct device connection is disabled (only aggregators can connect),
    we still have the remnants functionality of when we used to have this feature.
    """
    def __init__(self, area: "Area"):
        self.area: "Area" = area
        self._redis_communicator: Optional["ExternalConnectionCommunicator"] = None
        self.aggregator: Optional["AggregatorHandler"] = None
        self._connected: bool = False
        self.channel_names = ExternalStrategyChannels(
            gsy_e.constants.EXTERNAL_CONNECTION_WEB,
            gsy_e.constants.CONFIGURATION_ID,
            asset_uuid=self.area.uuid,
            asset_name=self.area.slug
        )

    @property
    def spot_market(self) -> "Market":
        """Return the "current" market (i.e. the one currently "running")"""
        return self.area.spot_market

    @property
    def is_aggregator_controlled(self) -> bool:
        """Return a boolean flag whether this market is controlled by an aggregator."""
        return self.aggregator and self.aggregator.is_controlling_device(self.area.uuid)

    @staticmethod
    def _get_transaction_id(payload: Dict) -> Optional[str]:
        """Extract the transaction_id from the received payload.

        Raises
            ValueError: The transaction id doesn't exist in the payload.
        """
        data = json.loads(payload["data"])
        if data.get("transaction_id"):
            return data["transaction_id"]
        raise ValueError("transaction_id not in payload or None")

    def _register(self, payload: Dict) -> None:
        """Callback for the register redis command."""
        self._connected = ExternalStrategyConnectionManager.register(
            self._redis_communicator, self.channel_names.register_response,
            self._connected, self._get_transaction_id(payload),
            area_uuid=self.area.uuid)

    def _unregister(self, payload: Dict) -> None:
        """Callback for the unregister redis command."""
        self._connected = ExternalStrategyConnectionManager.unregister(
            self._redis_communicator, self.channel_names.unregister_response,
            self._connected, self._get_transaction_id(payload))

    def sub_to_external_channels(self) -> None:
        """Subscribe to the redis channels and map callbacks (not used at the moment)."""
        self._redis_communicator = self.area.config.external_redis_communicator
        sub_channel_dict = {
            self.channel_names.dso_market_stats: self.dso_market_stats_callback,
            self.channel_names.grid_fees: self.set_grid_fees_callback,
            self.channel_names.register: self._register,
            self.channel_names.unregister: self._unregister}
        if self._redis_communicator.is_enabled:
            self.aggregator = self._redis_communicator.aggregator
        self._redis_communicator.sub_to_multiple_channels(sub_channel_dict)

    def set_grid_fees_callback(self, payload: Dict) -> Optional[Dict]:
        """Update the grid fees of the market."""
        if not (self._connected or self.is_aggregator_controlled):
            return None
        payload_data = (
            payload["data"] if isinstance(payload["data"], dict)
            else json.loads(payload["data"]))

        response = {"area_uuid": self.area.uuid,
                    "command": "grid_fees",
                    "status": "ready"}
        if (
           (payload_data.get("fee_const") is not None and self.area.config.grid_fee_type == 1) or
           (payload_data.get("fee_percent") is not None and self.area.config.grid_fee_type == 2)):
            try:
                self.area.area_reconfigure_event(
                    grid_fee_constant=payload_data.get("fee_const", None),
                    grid_fee_percentage=payload_data.get("fee_percent", None))
                response.update(
                    {"market_fee_const": str(self.area.grid_fee_constant),
                     "market_fee_percent": str(self.area.grid_fee_percentage)})
            except GSyAreaException as e:
                log.error(str(e))
                return None
        else:
            response.update({
                "status": "error",
                "error_message": "GridFee parameter conflicting with GlobalConfigFeeType"})

        if self.is_aggregator_controlled:
            return response
        response["transaction_id"] = payload_data.get("transaction_id", None)
        self._redis_communicator.publish_json(self.channel_names.grid_fees_response, response)
        return None

    def dso_market_stats_callback(self, payload: Dict) -> Optional[Dict]:
        """Return or publish the market stats."""
        if not (self._connected or self.is_aggregator_controlled):
            return None
        payload_data = (
            payload["data"] if isinstance(payload["data"], dict)
            else json.loads(payload["data"]))
        ret_val = {"status": "ready",
                   "name": self.area.name,
                   "area_uuid": self.area.uuid,
                   "command": "dso_market_stats",
                   "market_stats": self.area.stats.get_last_market_stats(dso=True)}
        if self.is_aggregator_controlled:
            return ret_val
        ret_val["transaction_id"] = payload_data.get("transaction_id", None)
        self._redis_communicator.publish_json(
            self.channel_names.dso_market_stats_response, ret_val)
        return None

    @property
    def _progress_info(self) -> Dict:
        """Return the progress information of the simulation."""
        slot_completion_percent = int((self.area.current_tick_in_slot /
                                       self.area.config.ticks_per_slot) * 100)
        return {"slot_completion": f"{slot_completion_percent}%",
                "market_slot": self.area.spot_market.time_slot_str}

    def publish_market_cycle(self):
        """Add the market cycle event to the area's aggregator events buffer."""
        if self.area.current_market is None:
            return

        if self.is_aggregator_controlled:
            self.aggregator.add_batch_market_event(self.area.uuid, self._progress_info)

    def deactivate(self):
        """Deactivate the area and notify the client/aggregator."""
        if self.is_aggregator_controlled:
            deactivate_msg = {"event": "finish"}
            self.aggregator.add_batch_finished_event(self.area.uuid, deactivate_msg)
        elif self._redis_communicator.is_enabled:
            deactivate_msg = {
                "event": "finish"
            }
            self._redis_communicator.publish_json(self.channel_names.finish, deactivate_msg)

    @property
    def _aggregator_command_callback_mapping(self) -> Dict:
        """Map the aggregator command types to their adjacent callbacks."""
        return {
            "grid_fees": self.set_grid_fees_callback,
            "dso_market_stats": self.dso_market_stats_callback
        }

    def trigger_aggregator_commands(self, command: Dict) -> Dict:
        """Receive an aggregator command and call the corresponding callback.

        Raises:
            CommandTypeNotSupported: The client sent a unsupported command
        """
        try:
            command_type = command.get("type")
            if command_type is None:
                return {
                    "status": "error",
                    "area_uuid": self.area.uuid,
                    "message": "Invalid command type"}

            callback = self._aggregator_command_callback_mapping.get(command["type"])
            if callback is None:
                return {
                    "command": command["type"], "status": "error",
                    "area_uuid": self.area.uuid,
                    "message": f"Command type not supported for device {self.area.uuid}"}
            response = callback(command)
        except CommandTypeNotSupported as e:
            response = {
                "command": command["type"], "status": "error",
                "area_uuid": self.area.uuid,
                "message": str(e)}
        return response
