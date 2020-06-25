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
from d3a.models.market.market_structures import Offer
from d3a_interface.constants_limits import ConstSettings
from d3a.d3a_core.singletons import aggregator


IncomingRequest = namedtuple('IncomingRequest', ('request_type', 'arguments', 'response_channel'))


class CommandTypeNotSupported(Exception):
    pass


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
    def is_aggregator_controlled(self):
        if not d3a.constants.EXTERNAL_CONNECTION_WEB:
            return False
        return aggregator.is_controlling_device(self.device.uuid)

    @property
    def should_use_default_strategy(self):
        return not self.connected and not self.is_aggregator_controlled

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

    def _device_info_aggregator(self, arguments):
        try:
            return {
                "command": "device_info", "status": "ready",
                "device_info": self._device_info_dict,
                "transaction_id": arguments.get("transaction_id", None),
                "area_uuid": self.device.uuid
            }
        except Exception as e:
            return {
                "command": "device_info", "status": "error",
                "error_message": f"Error when handling device info on area {self.device.name}.",
                "transaction_id": arguments.get("transaction_id", None),
                "area_uuid": self.device.uuid
            }

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
        if not self.connected and not self.is_aggregator_controlled:
            return

        current_tick = self.device.current_tick % self.device.config.ticks_per_slot
        if current_tick - self._last_dispatched_tick >= self._dispatch_tick_frequency:
            tick_event_channel = f"{self.channel_prefix}/events/tick"
            current_tick_info = {
                "event": "tick",
                "slot_completion":
                    f"{int((current_tick / self.device.config.ticks_per_slot) * 100)}%",
                "area_uuid": self.device.uuid,
                "device_info": self._device_info_dict
            }
            self._last_dispatched_tick = current_tick
            if self.connected:
                self.redis.publish_json(tick_event_channel, current_tick_info)

            if self.is_aggregator_controlled:
                aggregator.add_batch_tick_event(self.device.uuid, current_tick_info)

    def _publish_trade_event(self, trade, is_bid_trade):

        if trade.seller != self.device.name and \
                trade.buyer != self.device.name:
            # Trade does not concern this device, skip it.
            return

        if ConstSettings.IAASettings.MARKET_TYPE != 1 and \
                trade.buyer == self.device.name and \
                isinstance(trade.offer, Offer):
            # Do not track a 2-sided market trade that is originating from an Offer to a
            # consumer (which should have posted a bid). This occurs when the clearing
            # took place on the area market of the device, thus causing 2 trades, one for
            # the bid clearing and one for the offer clearing.
            return

        event_response_dict = {
            "device_info": self._device_info_dict,
            "event": "trade",
            "trade_id": trade.id,
            "time": trade.time.isoformat(),
            "price": trade.offer.price,
            "energy": trade.offer.energy,
            "fee_price": trade.fee_price,
            "area_uuid": self.device.uuid
        }
        event_response_dict["seller"] = trade.seller \
            if trade.seller == self.device.name else "anonymous"
        event_response_dict["buyer"] = trade.buyer \
            if trade.buyer == self.device.name else "anonymous"
        event_response_dict["residual_id"] = trade.residual.id \
            if trade.residual is not None else "None"
        bid_offer_key = 'bid_id' if is_bid_trade else 'offer_id'
        event_response_dict["event_type"] = "buy" \
            if trade.buyer == self.device.name else "sell"
        event_response_dict[bid_offer_key] = trade.offer.id
        trade_event_channel = f"{self.channel_prefix}/events/trade"
        if self.connected:
            self.redis.publish_json(trade_event_channel, event_response_dict)

        if self.is_aggregator_controlled:
            aggregator.add_batch_trade_event(self.device.uuid, event_response_dict)

    def event_bid_traded(self, market_id, bid_trade):
        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)
        if self.connected or aggregator.is_controlling_device(self.device.uuid):
            self._publish_trade_event(bid_trade, True)

    def event_trade(self, market_id, trade):
        super().event_trade(market_id=market_id, trade=trade)
        if self.connected or aggregator.is_controlling_device(self.device.uuid):
            self._publish_trade_event(trade, False)

    def deactivate(self):
        super().deactivate()
        if self.connected or aggregator.is_controlling_device(self.device.uuid):
            deactivate_event_channel = f"{self.channel_prefix}/events/finish"
            deactivate_msg = {
                "event": "finish",
                "area_uuid": self.device.uuid
            }
            if self.connected:
                self.redis.publish_json(deactivate_event_channel, deactivate_msg)

            if self.is_aggregator_controlled:
                aggregator.add_batch_finished_event(self.device.uuid, deactivate_msg)

    def _bid_aggregator(self, command):
        raise CommandTypeNotSupported(
            f"Bid command not supported on device {self.device.uuid}")

    def _delete_bid_aggregator(self, command):
        raise CommandTypeNotSupported(
            f"Delete bid command not supported on device {self.device.uuid}")

    def _list_bids_aggregator(self, command):
        raise CommandTypeNotSupported(
            f"List bids command not supported on device {self.device.uuid}")

    def _offer_aggregator(self, command):
        raise CommandTypeNotSupported(
            f"Offer command not supported on device {self.device.uuid}")

    def _delete_offer_aggregator(self, command):
        raise CommandTypeNotSupported(
            f"Delete offer command not supported on device {self.device.uuid}")

    def _list_offers_aggregator(self, command):
        raise CommandTypeNotSupported(
            f"List offers command not supported on device {self.device.uuid}")

    def trigger_aggregator_commands(self, command):
        if "type" not in command:
            return {
                "status": "error",
                "area_uuid": self.device.uuid,
                "message": "Invalid command type"}

        try:
            if command["type"] == "bid":
                return self._bid_aggregator(command)
            elif command["type"] == "delete_bid":
                return self._delete_bid_aggregator(command)
            elif command["type"] == "list_bids":
                return self._list_bids_aggregator(command)
            elif command["type"] == "offer":
                return self._offer_aggregator(command)
            elif command["type"] == "delete_offer":
                return self._delete_offer_aggregator(command)
            elif command["type"] == "list_offers":
                return self._list_offers_aggregator(command)
            elif command["type"] == "device_info":
                return self._device_info_aggregator(command)
            else:
                return {
                    "command": command["type"], "status": "error",
                    "area_uuid": self.device.uuid,
                    "message": f"Command type not supported for device {self.device.uuid}"}
        except CommandTypeNotSupported as e:
            return {
                "command": command["type"], "status": "error",
                "area_uuid": self.device.uuid,
                "message": str(e)}

    def _reject_all_pending_requests(self):
        for req in self.pending_requests:
            self.redis.publish_json(
                req.response_channel,
                {"command": "bid", "status": "error",
                 "error_message": f"Error when handling {req.request_type} "
                                  f"on area {self.device.name} with arguments {req.arguments}."
                                  f"Market cycle already finished."})
        self.pending_requests = []
