"""
Copyright 2018 Grid Singularity
This file is part of D3A.

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
import gsy_e
from logging import getLogger

from gsy_framework.area_validator import validate_area
from gsy_framework.utils import key_in_dict_and_not_none
from gsy_e.models.strategy.external_strategies import (
    CommandTypeNotSupported, ExternalStrategyConnectionManager)

log = getLogger(__name__)


class RedisMarketExternalConnection:
    def __init__(self, area):
        self.area = area
        self._redis_communicator = None
        self.aggregator = None
        self.connected = False

    @property
    def spot_market(self):
        return self.area.spot_market

    @property
    def is_aggregator_controlled(self):
        return self.aggregator and self.aggregator.is_controlling_device(self.area.uuid)

    @property
    def channel_prefix(self):
        if gsy_e.constants.EXTERNAL_CONNECTION_WEB:
            return f"external/{gsy_e.constants.CONFIGURATION_ID}/{self.area.uuid}"
        else:
            return f"{self.area.slug}"

    @staticmethod
    def _get_transaction_id(payload):
        data = json.loads(payload["data"])
        if key_in_dict_and_not_none(data, "transaction_id"):
            return data["transaction_id"]
        else:
            raise ValueError("transaction_id not in payload or None")

    def _register(self, payload):
        self._connected = ExternalStrategyConnectionManager.register(
            self._redis_communicator, self.channel_prefix,
            self.connected, self._get_transaction_id(payload),
            area_uuid=self.area.uuid)

    def _unregister(self, payload):
        self._connected = ExternalStrategyConnectionManager.unregister(
            self._redis_communicator, self.channel_prefix,
            self.connected, self._get_transaction_id(payload))

    def sub_to_external_channels(self):
        self._redis_communicator = self.area.config.external_redis_communicator
        sub_channel_dict = {
            f"{self.channel_prefix}/dso_market_stats": self.dso_market_stats_callback,
            f"{self.channel_prefix}/grid_fees": self.set_grid_fees_callback,
            f"{self.channel_prefix}/register_participant": self._register,
            f"{self.channel_prefix}/unregister_participant": self._unregister}
        if self.area.config.external_redis_communicator.is_enabled:
            self.aggregator = self.area.config.external_redis_communicator.aggregator
        self._redis_communicator.sub_to_multiple_channels(sub_channel_dict)

    def set_grid_fees_callback(self, payload):
        # TODO: This function should reuse the area_reconfigure_event function
        # since they share the same functionality.
        grid_fees_response_channel = f"{self.channel_prefix}/response/grid_fees"
        payload_data = payload["data"] \
            if isinstance(payload["data"], dict) else json.loads(payload["data"])
        try:
            validate_area(grid_fee_percentage=payload_data.get("fee_percent", None),
                          grid_fee_constant=payload_data.get("fee_const", None))
        except Exception as e:
            log.error(str(e))
            return

        base_dict = {"area_uuid": self.area.uuid,
                     "command": "grid_fees"}
        if "fee_const" in payload_data and payload_data["fee_const"] is not None and \
                self.area.config.grid_fee_type == 1:
            self.area.grid_fee_constant = payload_data["fee_const"]
            ret_val = {
                "status": "ready",
                "market_fee_const": str(self.area.grid_fee_constant),
                **base_dict}
        elif "fee_percent" in payload_data and payload_data["fee_percent"] is not None and \
                self.area.config.grid_fee_type == 2:
            self.area.grid_fee_percentage = payload_data["fee_percent"]
            ret_val = {
                "status": "ready",
                "market_fee_percent": str(self.area.grid_fee_percentage),
                **base_dict}
        else:
            ret_val = {
                "status": "error",
                "error_message": "GridFee parameter conflicting with GlobalConfigFeeType",
                **base_dict}

        self.area.should_update_child_strategies = True

        if self.is_aggregator_controlled:
            return ret_val
        else:
            ret_val["transaction_id"] = payload_data.get("transaction_id", None)
            self._redis_communicator.publish_json(grid_fees_response_channel, ret_val)

    def dso_market_stats_callback(self, payload):
        dso_market_stats_response_channel = f"{self.channel_prefix}/response/dso_market_stats"
        payload_data = payload["data"] \
            if isinstance(payload["data"], dict) else json.loads(payload["data"])
        ret_val = {"status": "ready",
                   'name': self.area.name,
                   "area_uuid": self.area.uuid,
                   "command": "dso_market_stats",
                   "market_stats": self.area.stats.get_last_market_stats(dso=True)}
        if self.is_aggregator_controlled:
            return ret_val
        else:
            ret_val["transaction_id"] = payload_data.get("transaction_id", None)
            self._redis_communicator.publish_json(dso_market_stats_response_channel, ret_val)

    @property
    def _progress_info(self):
        slot_completion_percent = int((self.area.current_tick_in_slot /
                                       self.area.config.ticks_per_slot) * 100)
        return {'slot_completion': f'{slot_completion_percent}%',
                'market_slot': self.area.spot_market.time_slot_str}

    def publish_market_cycle(self):
        if self.area.current_market is None:
            return

        if self.is_aggregator_controlled:
            self.aggregator.add_batch_market_event(self.area.uuid, self._progress_info)

    def deactivate(self):
        if self.is_aggregator_controlled:
            deactivate_msg = {'event': 'finish'}
            self.aggregator.add_batch_finished_event(self.area.uuid, deactivate_msg)
        elif self._redis_communicator.is_enabled:
            deactivate_event_channel = f"{self.channel_prefix}/events/finish"
            deactivate_msg = {
                "event": "finish"
            }
            self._redis_communicator.publish_json(deactivate_event_channel, deactivate_msg)

    def trigger_aggregator_commands(self, command):
        if "type" not in command:
            return {
                "status": "error",
                "area_uuid": self.area.uuid,
                "message": "Invalid command type"}

        try:
            if command["type"] == "grid_fees":
                return self.set_grid_fees_callback(command)
            elif command["type"] == "dso_market_stats":
                return self.dso_market_stats_callback(command)
            else:
                return {
                    "command": command["type"], "status": "error",
                    "area_uuid": self.area.uuid,
                    "message": f"Command type not supported for device {self.area.uuid}"}
        except CommandTypeNotSupported as e:
            return {
                "command": command["type"], "status": "error",
                "area_uuid": self.area.uuid,
                "message": str(e)}
