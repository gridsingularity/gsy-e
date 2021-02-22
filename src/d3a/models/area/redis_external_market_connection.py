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
import d3a
from logging import getLogger

from d3a_interface.area_validator import validate_area
from d3a_interface.utils import key_in_dict_and_not_none
from d3a.models.strategy.external_strategies import CommandTypeNotSupported, register_area, \
    unregister_area

log = getLogger(__name__)


class RedisMarketExternalConnection:
    def __init__(self, area):
        self.area = area
        self.redis_com = None
        self.aggregator = None
        self.connected = False

    @property
    def next_market(self):
        return self.area.next_market

    @property
    def is_aggregator_controlled(self):
        return self.aggregator.is_controlling_device(self.area.uuid)

    @property
    def channel_prefix(self):
        if d3a.constants.EXTERNAL_CONNECTION_WEB:
            return f"external/{d3a.constants.COLLABORATION_ID}/{self.area.uuid}"
        else:
            return f"{self.area.slug}"

    @property
    def _market_stats_channel(self):
        return f"{self.channel_prefix}/market_stats"

    @property
    def _grid_fees_channel(self):
        return f"{self.channel_prefix}/grid_fees"

    @staticmethod
    def _get_transaction_id(payload):
        data = json.loads(payload["data"])
        if key_in_dict_and_not_none(data, "transaction_id"):
            return data["transaction_id"]
        else:
            raise ValueError("transaction_id not in payload or None")

    def _register(self, payload):
        self._connected = register_area(self.redis_com, self.channel_prefix, self.connected,
                                        self._get_transaction_id(payload),
                                        area_uuid=self.area.uuid)

    def _unregister(self, payload):
        self._connected = unregister_area(self.redis_com, self.channel_prefix, self.connected,
                                          self._get_transaction_id(payload))

    def sub_to_external_channels(self):
        self.redis_com = self.area.config.external_redis_communicator
        sub_channel_dict = {
            f"{self.channel_prefix}/market_stats": self.market_stats_callback,
            f"{self.channel_prefix}/dso_market_stats": self.dso_market_stats_callback,
            f"{self.channel_prefix}/grid_fees": self.set_grid_fees_callback,
            f"{self.channel_prefix}/register_participant": self._register,
            f"{self.channel_prefix}/unregister_participant": self._unregister}
        if self.area.config.external_redis_communicator.is_enabled:
            self.aggregator = self.area.config.external_redis_communicator.aggregator
        self.redis_com.sub_to_multiple_channels(sub_channel_dict)

    def market_stats_callback(self, payload):
        market_stats_response_channel = f"{self.channel_prefix}/response/market_stats"
        payload_data = payload["data"] \
            if isinstance(payload["data"], dict) else json.loads(payload["data"])
        ret_val = {"status": "ready",
                   'name': self.area.name,
                   "area_uuid": self.area.uuid,
                   "command": "market_stats",
                   "market_stats":
                       self.area.stats.get_last_market_stats()}
        if self.is_aggregator_controlled:
            return ret_val
        else:
            ret_val["transaction_id"] = payload_data.get("transaction_id", None)
            self.redis_com.publish_json(market_stats_response_channel, ret_val)

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
            self.redis_com.publish_json(grid_fees_response_channel, ret_val)

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
            self.redis_com.publish_json(dso_market_stats_response_channel, ret_val)

    def event_market_cycle(self):
        if self.area.current_market is None:
            return
        market_event_channel = f"{self.channel_prefix}/market-events/market"
        market_info = self.next_market.info
        market_info["current_market_fee"] = \
            self.area.current_market.fee_class.grid_fee_rate
        market_info["next_market_fee"] = self.area.get_grid_fee()
        market_info["last_market_stats"] = \
            self.area.stats.get_price_stats_current_market()
        market_info["self_sufficiency"] = \
            self.area.stats.kpi.get("self_sufficiency", None)
        market_info["area_uuid"] = self.area.uuid
        if self.is_aggregator_controlled:
            market_info["event"] = "market"
            market_info["status"] = "ready"
            self.aggregator.add_batch_market_event(self.area.uuid, market_info,
                                                   self.area.global_objects)
        else:
            data = {"status": "ready",
                    "event": "market",
                    "market_info": market_info}
            self.redis_com.publish_json(market_event_channel, data)

    def deactivate(self):
        deactivate_event_channel = f"{self.channel_prefix}/events/finish"
        deactivate_msg = {
            "event": "finish"
        }
        if self.is_aggregator_controlled:
            self.aggregator.add_batch_finished_event(self.area.uuid, deactivate_msg)
        else:
            self.redis_com.publish_json(deactivate_event_channel, deactivate_msg)

    def trigger_aggregator_commands(self, command):
        if "type" not in command:
            return {
                "status": "error",
                "area_uuid": self.area.uuid,
                "message": "Invalid command type"}

        try:
            if command["type"] == "grid_fees":
                return self.set_grid_fees_callback(command)
            elif command["type"] == "market_stats":
                return self.market_stats_callback(command)
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
