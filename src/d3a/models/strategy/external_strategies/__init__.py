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
import logging
from collections import deque, namedtuple
from threading import Lock
from typing import Dict

from d3a_interface.constants_limits import ConstSettings
from d3a_interface.utils import (key_in_dict_and_not_none, convert_str_to_pendulum_in_dict,
                                 str_to_pendulum_datetime)
from pendulum import DateTime

import d3a.constants
from d3a.gsy_core.global_objects_singleton import global_objects

IncomingRequest = namedtuple("IncomingRequest", ("request_type", "arguments", "response_channel"))

default_market_info = {"device_info": None,
                       "asset_bill": None,
                       "event": None,
                       "grid_stats_tree": None,
                       "area_uuid": None}


class CommandTypeNotSupported(Exception):
    pass


def check_for_connected_and_reply(redis, channel_name, is_connected):
    if not is_connected:
        redis.publish_json(
            channel_name, {
                "status": "error",
                "error_message": "Client should be registered in order to access this area."})
        return False
    return True


def register_area(redis, channel_prefix, is_connected, transaction_id, area_uuid=None):
    register_response_channel = f"{channel_prefix}/response/register_participant"
    try:
        redis.publish_json(
            register_response_channel,
            {"command": "register", "status": "ready", "registered": True,
             "transaction_id": transaction_id, "device_uuid": area_uuid})
        return True
    except Exception:
        logging.exception(f"Error when registering to area {channel_prefix}")
        redis.publish_json(
            register_response_channel,
            {"command": "register", "status": "error", "transaction_id": transaction_id,
             "device_uuid": area_uuid,
             "error_message": f"Error when registering to area {channel_prefix}."})
        return is_connected


def unregister_area(redis, channel_prefix, is_connected, transaction_id):
    unregister_response_channel = f"{channel_prefix}/response/unregister_participant"
    if not check_for_connected_and_reply(redis, unregister_response_channel,
                                         is_connected):
        return
    try:
        redis.publish_json(
            unregister_response_channel,
            {"command": "unregister", "status": "ready", "unregistered": True,
             "transaction_id": transaction_id})
        return False
    except Exception:
        logging.exception(f"Error when unregistering from area {channel_prefix}")
        redis.publish_json(
            unregister_response_channel,
            {"command": "unregister", "status": "error", "transaction_id": transaction_id,
             "error_message": f"Error when unregistering from area {channel_prefix}."})
        return is_connected


class ExternalMixin:

    def __init__(self, *args, **kwargs):
        self._connected = False
        self.connected = False
        self._use_template_strategy = False
        super().__init__(*args, **kwargs)
        self._last_dispatched_tick = 0
        self.pending_requests = deque()
        self.lock = Lock()

    def get_state(self):
        strategy_state = super().get_state()
        strategy_state.update({
            "connected": self.connected,
            "use_template_strategy": self._use_template_strategy
        })
        return strategy_state

    def restore_state(self, state_dict):
        super().restore_state(state_dict)
        self._connected = state_dict.get("connected", False)
        self.connected = state_dict.get("connected", False)
        self._use_template_strategy = state_dict.get("use_template_strategy", False)

    @property
    def channel_dict(self):
        return {
            f"{self.channel_prefix}/register_participant": self._register,
            f"{self.channel_prefix}/unregister_participant": self._unregister,
            f"{self.channel_prefix}/device_info": self._device_info,
        }

    @property
    def channel_prefix(self):
        if d3a.constants.EXTERNAL_CONNECTION_WEB:
            return f"external/{d3a.constants.CONFIGURATION_ID}/{self.device.uuid}"
        else:
            return f"{self.device.name}"

    @property
    def is_aggregator_controlled(self):
        return (self.redis.aggregator is not None
                and self.redis.aggregator.is_controlling_device(self.device.uuid))

    def _remove_area_uuid_from_aggregator_mapping(self):
        self.redis.aggregator.device_aggregator_mapping.pop(self.device.uuid, None)

    @property
    def should_use_default_strategy(self):
        return self._use_template_strategy or \
               not (self.connected or self.is_aggregator_controlled)

    @staticmethod
    def _get_transaction_id(payload):
        data = json.loads(payload["data"])
        if key_in_dict_and_not_none(data, "transaction_id"):
            return data["transaction_id"]
        else:
            raise ValueError("transaction_id not in payload or None")

    def area_reconfigure_event(self, *args, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        if key_in_dict_and_not_none(kwargs, "allow_external_connection"):
            self._use_template_strategy = not kwargs["allow_external_connection"]
        super().area_reconfigure_event(*args, **kwargs)

    def _register(self, payload):
        self._connected = register_area(self.redis, self.channel_prefix, self.connected,
                                        self._get_transaction_id(payload),
                                        area_uuid=self.device.uuid)

    def _unregister(self, payload):
        self._connected = unregister_area(self.redis, self.channel_prefix, self.connected,
                                          self._get_transaction_id(payload))

    def register_on_market_cycle(self):
        if self.connected is True and self._connected is False:
            self._remove_area_uuid_from_aggregator_mapping()
        self.connected = self._connected

    def _device_info(self, payload):
        device_info_response_channel = f"{self.channel_prefix}/response/device_info"
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
                 "transaction_id": arguments.get("transaction_id")})
        except Exception:
            error_message = f"Error when handling device info on area {self.device.name}"
            logging.exception(error_message)
            self.redis.publish_json(
                response_channel,
                {"command": "device_info", "status": "error",
                 "error_message": error_message,
                 "transaction_id": arguments.get("transaction_id")})

    def _device_info_aggregator(self, arguments):
        try:
            return {
                "command": "device_info", "status": "ready",
                "device_info": self._device_info_dict,
                "transaction_id": arguments.get("transaction_id"),
                "area_uuid": self.device.uuid
            }
        except Exception:
            return {
                "command": "device_info", "status": "error",
                "error_message": f"Error when handling device info on area {self.device.name}.",
                "transaction_id": arguments.get("transaction_id"),
                "area_uuid": self.device.uuid
            }

    @property
    def spot_market(self):
        return self.market_area.spot_market

    def _get_market_from_command_argument(self, arguments: Dict):
        if arguments.get("time_slot") is None:
            return self.spot_market
        time_slot = str_to_pendulum_datetime(arguments["time_slot"])
        return self._get_market_from_time_slot(time_slot)

    def _get_market_from_time_slot(self, time_slot: DateTime):
        market = self.market_area.get_market(time_slot)
        if market:
            return market
        market = self.market_area.get_settlement_market(time_slot)
        if not market:
            raise Exception(f"Timeslot {time_slot} is not currently in the spot, future or "
                            f"settlement markets")
        return market

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

    @property
    def _progress_info(self):
        slot_completion_percent = int((self.device.current_tick_in_slot /
                                       self.device.config.ticks_per_slot) * 100)
        return {"slot_completion": f"{slot_completion_percent}%",
                "market_slot": self.area.spot_market.time_slot_str}

    def _dispatch_event_tick_to_external_agent(self):
        if global_objects.external_global_stats.\
                is_it_time_for_external_tick(self.device.current_tick):
            if self.is_aggregator_controlled:
                self.redis.aggregator.add_batch_tick_event(self.device.uuid, self._progress_info)
            elif self.connected:
                tick_event_channel = f"{self.channel_prefix}/events/tick"
                current_tick_info = {
                    **self._progress_info,
                    "event": "tick",
                    "area_uuid": self.device.uuid,
                    "device_info": self._device_info_dict
                }
                self.redis.publish_json(tick_event_channel, current_tick_info)

    def event_market_cycle(self):
        if self.should_use_default_strategy:
            super().event_market_cycle()

    def publish_market_cycle(self):
        if not self.should_use_default_strategy and self.is_aggregator_controlled:
            self.redis.aggregator.add_batch_market_event(self.device.uuid, self._progress_info)

    def _publish_trade_event(self, trade, is_bid_trade):

        if trade.seller != self.device.name and \
                trade.buyer != self.device.name:
            # Trade does not concern this device, skip it.
            return

        if ConstSettings.IAASettings.MARKET_TYPE != 1 and \
                ((trade.buyer == self.device.name and trade.is_offer_trade) or
                 (trade.seller == self.device.name and trade.is_bid_trade)):
            # Do not track a 2-sided market trade that is originating from an Offer to a
            # consumer (which should have posted a bid). This occurs when the clearing
            # took place on the area market of the device, thus causing 2 trades, one for
            # the bid clearing and one for the offer clearing.
            return

        if self.is_aggregator_controlled:
            event_response_dict = {"event": "trade",
                                   "asset_id": self.device.uuid,
                                   "trade_id": trade.id,
                                   "time": trade.time.isoformat(),
                                   "trade_price": trade.offer_bid.price,
                                   "traded_energy": trade.offer_bid.energy,
                                   "total_fee": trade.fee_price,
                                   "local_market_fee":
                                       self.area.current_market.fee_class.grid_fee_rate
                                       if self.area.current_market is not None else "None",
                                   "attributes": trade.offer_bid.attributes,
                                   "seller": trade.seller
                                   if trade.seller_id == self.device.uuid else "anonymous",
                                   "buyer": trade.buyer
                                   if trade.buyer_id == self.device.uuid else "anonymous",
                                   "seller_origin": trade.seller_origin,
                                   "buyer_origin": trade.buyer_origin,
                                   "bid_id": trade.offer_bid.id
                                   if trade.is_bid_trade else "None",
                                   "offer_id": trade.offer_bid.id
                                   if trade.is_offer_trade else "None",
                                   "residual_bid_id": trade.residual.id
                                   if trade.residual is not None and trade.is_bid_trade
                                   else "None",
                                   "residual_offer_id": trade.residual.id
                                   if trade.residual is not None and trade.is_offer_trade
                                   else "None"}

            global_objects.external_global_stats.update()
            self.redis.aggregator.add_batch_trade_event(self.device.uuid, event_response_dict)
        elif self.connected:
            event_response_dict = {"device_info": self._device_info_dict,
                                   "event": "trade",
                                   "trade_id": trade.id,
                                   "time": trade.time.isoformat(),
                                   "trade_price": trade.offer_bid.price,
                                   "traded_energy": trade.offer_bid.energy,
                                   "fee_price": trade.fee_price,
                                   "area_uuid": self.device.uuid,
                                   "seller": trade.seller
                                   if trade.seller == self.device.name else "anonymous",
                                   "buyer": trade.buyer
                                   if trade.buyer == self.device.name else "anonymous",
                                   "residual_id": trade.residual.id
                                   if trade.residual is not None else "None"}

            bid_offer_key = "bid_id" if is_bid_trade else "offer_id"
            event_response_dict["event_type"] = (
                "buy" if trade.buyer == self.device.name else "sell")
            event_response_dict[bid_offer_key] = trade.offer_bid.id

            trade_event_channel = f"{self.channel_prefix}/events/trade"
            self.redis.publish_json(trade_event_channel, event_response_dict)

    def event_bid_traded(self, market_id, bid_trade):
        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)
        if self.connected or self.is_aggregator_controlled:
            self._publish_trade_event(bid_trade, True)

    def event_offer_traded(self, market_id, trade):
        super().event_offer_traded(market_id=market_id, trade=trade)
        if self.connected or self.is_aggregator_controlled:
            self._publish_trade_event(trade, False)

    def deactivate(self):
        super().deactivate()

        if self.is_aggregator_controlled:
            deactivate_msg = {"event": "finish"}
            self.redis.aggregator.add_batch_finished_event(self.owner.uuid, deactivate_msg)
        elif self.connected:
            deactivate_event_channel = f"{self.channel_prefix}/events/finish"
            deactivate_msg = {
                "event": "finish",
                "area_uuid": self.device.uuid
            }
            self.redis.publish_json(deactivate_event_channel, deactivate_msg)

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
            elif command["type"] == "set_energy_forecast":
                return self._set_energy_forecast_aggregator(command)
            elif command["type"] == "set_energy_measurement":
                return self._set_energy_measurement_aggregator(command)
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
                {"command": f"{req.request_type}", "status": "error",
                 "error_message": f"Error when handling {req.request_type} "
                                  f"on area {self.device.name} with arguments {req.arguments}."
                                  f"Market cycle already finished."})
        self.pending_requests = deque()

    def set_energy_forecast(self, payload: Dict) -> None:
        """Callback for set_energy_forecast redis endpoint."""
        self.set_device_energy_data(payload, "set_energy_forecast", "energy_forecast")

    def set_energy_measurement(self, payload: Dict) -> None:
        """Callback for set_energy_measurement redis endpoint."""
        self.set_device_energy_data(payload, "set_energy_measurement", "energy_measurement")

    def set_device_energy_data(self, payload: Dict, command_type: str,
                               energy_data_arg_name: str) -> None:
        transaction_id = self._get_transaction_id(payload)
        energy_data_response_channel = \
            f"{self.channel_prefix}/response/{command_type}"
        # Deactivating register/connected requirement for power forecasts.
        # if not check_for_connected_and_reply(self.redis, power_forecast_response_channel,
        #                                      self.connected):
        #     return
        try:
            arguments = json.loads(payload["data"])
            assert set(arguments.keys()) == {energy_data_arg_name, "transaction_id"}
        except Exception:
            logging.exception(
                f"Incorrect {command_type} request: Payload {payload}")
            self.redis.publish_json(
                energy_data_response_channel,
                {"command": command_type,
                 "error": f"Incorrect {command_type} request. "
                          f"Available parameters: ({energy_data_arg_name}).",
                 "transaction_id": transaction_id})
        else:
            self.pending_requests.append(
                IncomingRequest(command_type, arguments,
                                energy_data_response_channel))

    def set_energy_forecast_impl(self, arguments: Dict, response_channel: str) -> None:
        self._set_device_energy_data_impl(arguments, response_channel, "set_energy_forecast")

    def set_energy_measurement_impl(self, arguments: Dict, response_channel: str) -> None:
        self._set_device_energy_data_impl(arguments, response_channel, "set_energy_measurement")

    def _set_device_energy_data_impl(self, arguments: Dict, response_channel: str,
                                     command_type: str) -> None:
        """
        Digest command from buffer and perform set_energy_forecast or set_energy_measurement.
        Args:
            arguments: Dictionary containing "energy_forecast/energy_measurement" that is a dict
                containing a profile
                key: time string, value: energy in kWh
            response_channel: redis channel string where the response should be sent to
        """
        try:
            self._set_device_energy_data_state(command_type, arguments)

            self.redis.publish_json(
                response_channel,
                {"command": command_type, "status": "ready",
                 "transaction_id": arguments.get("transaction_id")})
        except Exception:
            error_message = (f"Error when handling _{command_type}_impl "
                             f"on area {self.device.name}. Arguments: {arguments}")
            logging.exception(error_message)
            self.redis.publish_json(
                response_channel,
                {"command": command_type, "status": "error",
                 "error_message": error_message,
                 "transaction_id": arguments.get("transaction_id")})

    def _set_energy_forecast_aggregator(self, arguments):
        return self._set_device_energy_data_aggregator(arguments, "set_energy_forecast")

    def _set_energy_measurement_aggregator(self, arguments):
        return self._set_device_energy_data_aggregator(arguments, "set_energy_measurement")

    def _set_device_energy_data_aggregator(self, arguments, command_name):
        try:
            self._set_device_energy_data_state(command_name, arguments)
            return {
                "command": command_name, "status": "ready",
                command_name: arguments,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except Exception:
            logging.exception(f"Error when handling bid on area {self.device.name}")
            return {
                "command": command_name, "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling {command_name} "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id")}

    @staticmethod
    def _validate_values_positive_in_profile(profile: Dict) -> None:
        """Validate whether all values are positive in a profile."""
        for time_str, energy in profile.items():
            if energy < 0.0:
                raise ValueError(f"Energy is not positive for time stamp {time_str}.")

    def _set_device_energy_data_state(self, command_type: str, arguments: Dict) -> None:
        if command_type == "set_energy_forecast":
            self._validate_values_positive_in_profile(arguments["energy_forecast"])
            self.energy_forecast_buffer.update(
                convert_str_to_pendulum_in_dict(arguments["energy_forecast"]))
        elif command_type == "set_energy_measurement":
            self._validate_values_positive_in_profile(arguments["energy_measurement"])
            self.energy_measurement_buffer.update(
                convert_str_to_pendulum_in_dict(arguments["energy_measurement"]))
        else:
            assert False, f"Unsupported command {command_type}, available commands: " \
                          f"set_energy_forecast, set_energy_measurement"

    @property
    def market_info_dict(self):
        return {"asset_info": self._device_info_dict,
                "last_slot_asset_info": self.last_slot_asset_info,
                "asset_bill": self.device.stats.aggregated_stats["bills"]
                if "bills" in self.device.stats.aggregated_stats else None
                }

    @property
    def last_slot_asset_info(self):
        return {
                "energy_traded": self.energy_traded(self.area.current_market.id)
                if self.area.current_market else None,
                "total_cost": self.energy_traded_costs(self.area.current_market.id)
                if self.area.current_market else None,
                }
