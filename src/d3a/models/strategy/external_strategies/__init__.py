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
import logging
import json
import d3a.constants
from d3a.constants import DISPATCH_EVENT_TICK_FREQUENCY_PERCENT
from collections import namedtuple


IncomingRequest = namedtuple('IncomingRequest', ('request_type', 'arguments', 'response_channel'))


def check_for_connected_and_reply(redis, channel_name, is_connected):
    if not is_connected:
        redis.publish_json(
            channel_name, {
                "status": "error",
                "error_message": f"Client should be registered in order to access this area."})
        return False
    return True


def register_area(redis, channel_prefix, is_connected, transaction_id):
    register_response_channel = f'{channel_prefix}/response/register_participant'
    try:
        redis.publish_json(
            register_response_channel,
            {"command": "register", "status": "ready", "registered": True,
             "transaction_id": transaction_id})
        return True
    except Exception as e:
        logging.error(f"Error when registering to area {channel_prefix}: "
                      f"Exception: {str(e)}")
        redis.publish_json(
            register_response_channel,
            {"command": "register", "status": "error", "transaction_id": transaction_id,
             "error_message": f"Error when registering to area {channel_prefix}."})
        return is_connected


def unregister_area(redis, channel_prefix, is_connected, transaction_id):
    unregister_response_channel = f'{channel_prefix}/response/unregister_participant'
    if not check_for_connected_and_reply(redis, unregister_response_channel,
                                         is_connected):
        return
    try:
        redis.publish_json(
            unregister_response_channel,
            {"command": "unregister", "status": "ready", "unregistered": True,
             "transaction_id": transaction_id})
        return False
    except Exception as e:
        logging.error(f"Error when unregistering from area {channel_prefix}: "
                      f"Exception: {str(e)}")
        redis.publish_json(
            unregister_response_channel,
            {"command": "unregister", "status": "error", "transaction_id": transaction_id,
             "error_message": f"Error when unregistering from area {channel_prefix}."})
        return is_connected


class ExternalMixin:
    def __init__(self, *args, **kwargs):
        self._connected = False
        self.connected = False
        super().__init__(*args, **kwargs)
        self._last_dispatched_tick = 0
        self.pending_requests = []

    @property
    def channel_prefix(self):
        if d3a.constants.EXTERNAL_CONNECTION_WEB:
            return f"external/{d3a.constants.COLLABORATION_ID}/{self.device.uuid}"
        else:
            return f"{self.device.name}"

    @property
    def _dispatch_tick_frequency(self):
        return int(
            self.device.config.ticks_per_slot *
            (DISPATCH_EVENT_TICK_FREQUENCY_PERCENT / 100)
        )

    @staticmethod
    def _get_transaction_id(payload):
        data = json.loads(payload["data"])
        if "transaction_id" in data and data["transaction_id"] is not None:
            return data["transaction_id"]
        else:
            raise ValueError("transaction_id not in payload or None")

    def _register(self, payload):
        self._connected = register_area(self.redis, self.channel_prefix, self.connected,
                                        self._get_transaction_id(payload))

    def _unregister(self, payload):
        self._connected = unregister_area(self.redis, self.channel_prefix, self.connected,
                                          self._get_transaction_id(payload))

    def register_on_market_cycle(self):
        self.connected = self._connected

    def _device_info(self, payload):
        device_info_response_channel = f'{self.channel_prefix}/response/device_info'
        if not check_for_connected_and_reply(self.redis, device_info_response_channel,
                                             self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("device_info", arguments, device_info_response_channel))

    def _device_info_impl(self, arguments, response_channel):
        try:
            self.redis.publish_json(
                response_channel,
                {"command": "device_info", "status": "ready",
                 "device_info": self._device_info_dict,
                 "transaction_id": arguments.get("transaction_id", None)})
        except Exception as e:
            logging.error(f"Error when handling device info on area {self.device.name}: "
                          f"Exception: {str(e)}")
            self.redis.publish_json(
                response_channel,
                {"command": "device_info", "status": "error",
                 "error_message": f"Error when handling device info on area {self.device.name}.",
                 "transaction_id": arguments.get("transaction_id", None)})

    @property
    def market(self):
        return self.market_area.next_market

    @property
    def market_area(self):
        return self.area

    @property
    def device(self):
        return self.owner

    @property
    def redis(self):
        return self.owner.config.external_redis_communicator

    @property
    def _device_info_dict(self):
        return {}

    def _reset_event_tick_counter(self):
        self._last_dispatched_tick = 0

    def _dispatch_event_tick_to_external_agent(self):
        current_tick = self.device.current_tick_in_slot % self.device.config.ticks_per_slot
        if current_tick - self._last_dispatched_tick >= self._dispatch_tick_frequency:
            tick_event_channel = f"{self.channel_prefix}/events/tick"
            current_tick_info = {
                "event": "tick",
                "slot_completion":
                    f"{int((current_tick / self.device.config.ticks_per_slot) * 100)}%",
                "device_info": self._device_info_dict
            }
            self._last_dispatched_tick = current_tick
            self.redis.publish_json(tick_event_channel, current_tick_info)

    def event_trade(self, market_id, trade):
        super().event_trade(market_id=market_id, trade=trade)
        if self.connected:
            trade_dict = json.loads(trade.to_JSON_string())
            trade_dict.pop('already_tracked', None)
            trade_dict.pop('offer_bid_trade_info', None)
            trade_dict.pop('seller_origin', None)
            trade_dict.pop('buyer_origin', None)
            trade_dict["device_info"] = self._device_info_dict
            trade_dict["event"] = "trade"
            trade_event_channel = f"{self.channel_prefix}/events/trade"
            self.redis.publish_json(trade_event_channel, trade_dict)

    def deactivate(self):
        super().deactivate()
        if self.connected:
            deactivate_event_channel = f"{self.channel_prefix}/events/finish"
            deactivate_msg = {
                "event": "finish"
            }
            self.redis.publish_json(deactivate_event_channel, deactivate_msg)

    def _reject_all_pending_requests(self):
        for req in self.pending_requests:
            self.redis.publish_json(
                req.response_channel,
                {"command": "bid", "status": "error",
                 "error_message": f"Error when handling {req.request_type} "
                                  f"on area {self.device.name} with arguments {req.arguments}."
                                  f"Market cycle already finished."})
        self.pending_requests = []
