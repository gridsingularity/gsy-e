import json
import logging
from copy import deepcopy
from threading import Lock

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import SpotMarketTypeEnum
from gsy_framework.redis_channels import AggregatorChannels
from gsy_framework.utils import create_subdict_or_update
from redis import Redis

import gsy_e.constants
from gsy_e.gsy_e_core.global_objects_singleton import global_objects


class AggregatorHandler:
    # pylint: disable=too-many-instance-attributes
    """
    Handles event sending, command responses to all connected aggregators
    """

    def __init__(self, redis_db: Redis):
        self.redis_db = redis_db
        self.pubsub = self.redis_db.pubsub()
        self.pending_batch_commands = {}
        self.processing_batch_commands = {}
        self.responses_batch_commands = {}
        self.batch_market_cycle_events = {}
        self.batch_tick_events = {}
        self.batch_trade_events = {}
        self.batch_finished_events = {}
        self.aggregator_device_mapping = {}
        self.device_aggregator_mapping = {}
        self.lock = Lock()
        self.grid_buffer = {}

    def set_aggregator_device_mapping(self, aggregator_device):
        """Sets the aggregator_device_mapping derived from the aggregator_device_mapping
        that was sent when starting the simulation"""
        self.aggregator_device_mapping = aggregator_device
        self.device_aggregator_mapping = {
            dev: aggr
            for aggr, devices in self.aggregator_device_mapping.items()
            for dev in devices
        }

    def is_controlling_device(self, device_uuid):
        """Return if the aggregator is controlling the device with specified uuid."""
        return device_uuid in self.device_aggregator_mapping

    def _add_batch_event(self, device_uuid: str, event: dict, batch_event_dict: dict):
        """Add a batch event dict to the respective event buffer"""
        aggregator_uuid = self.device_aggregator_mapping[device_uuid]
        create_subdict_or_update(batch_event_dict, aggregator_uuid, event)

    def _delete_not_owned_devices_from_dict(self, area_stats_tree_dict, aggregator_uuid):
        """Wrapper for _delete_not_owned_devices"""
        out_dict = deepcopy(area_stats_tree_dict)
        self._delete_not_owned_devices(area_stats_tree_dict, aggregator_uuid, out_dict)
        return out_dict

    def _delete_not_owned_devices(self, indict: dict, aggregator_uuid: str, outdict: dict):
        """Only sent area info from areas that are connected to an external client and
        to the same aggregator from the to be sent area_stats_tree_dict"""
        for area_uuid, area_dict in indict.items():
            if "children" in area_dict:
                self._delete_not_owned_devices(
                    indict[area_uuid]["children"], aggregator_uuid, outdict[area_uuid]["children"]
                )
            else:
                if (
                    area_uuid not in self.device_aggregator_mapping
                    or area_uuid not in self.aggregator_device_mapping[aggregator_uuid]
                ):
                    outdict[area_uuid] = {"area_name": area_dict["area_name"]}

    def _create_grid_tree_event_dict(self, aggregator_uuid: str) -> dict:
        """Accumulate area_stats_tree_dict information and initiate a event dictionary
        to be sent to the client"""
        if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.COEFFICIENTS.value:
            return {"grid_tree": global_objects.scm_external_global_stats.area_stats_tree_dict}
        return {
            "grid_tree": self._delete_not_owned_devices_from_dict(
                global_objects.external_global_stats.area_stats_tree_dict, aggregator_uuid
            ),
            "feed_in_tariff_rate": global_objects.external_global_stats.current_feed_in_tariff,
            "market_maker_rate": global_objects.external_global_stats.current_market_maker_rate,
        }

    def add_batch_market_event(self, device_uuid: str, market_info: dict):
        """Add market_cycle event to the event buffer."""
        aggregator_uuid = self.device_aggregator_mapping[device_uuid]
        market_info.update(self._create_grid_tree_event_dict(aggregator_uuid))
        self._add_batch_event(device_uuid, market_info, self.batch_market_cycle_events)

    def add_batch_tick_event(self, device_uuid: str, tick_info: dict):
        """Add tick event to the event buffer."""
        aggregator_uuid = self.device_aggregator_mapping[device_uuid]
        tick_info.update(self._create_grid_tree_event_dict(aggregator_uuid))
        self._add_batch_event(device_uuid, tick_info, self.batch_tick_events)

    def add_batch_finished_event(self, device_uuid: str, finish_info: dict):
        """Add finish event to the event buffer."""
        self._add_batch_event(device_uuid, finish_info, self.batch_finished_events)

    def add_batch_trade_event(self, device_uuid: str, trade_info: dict):
        """Add trade event to the event buffer."""
        aggregator_uuid = self.device_aggregator_mapping[device_uuid]
        if aggregator_uuid not in self.batch_trade_events:
            self.batch_trade_events[aggregator_uuid] = {"trade_list": []}

        self.batch_trade_events[aggregator_uuid].update(
            self._create_grid_tree_event_dict(aggregator_uuid)
        )
        self.batch_trade_events[aggregator_uuid]["trade_list"].append(trade_info)

    def aggregator_callback(self, payload):
        """Entrypoint for aggregator related commands"""
        message = json.loads(payload["data"])
        if (
            gsy_e.constants.EXTERNAL_CONNECTION_WEB is True
            and message["config_uuid"] != gsy_e.constants.CONFIGURATION_ID
        ):
            return
        if message["type"] == "CREATE":
            self._create_aggregator(message)
        elif message["type"] == "DELETE":
            self._delete_aggregator(message)
        elif message["type"] == "SELECT":
            self._select_aggregator(message)
        elif message["type"] == "UNSELECT":
            self._unselect_aggregator(message)

    def _select_aggregator(self, message):
        if message["aggregator_uuid"] not in self.aggregator_device_mapping:
            self.aggregator_device_mapping[message["aggregator_uuid"]] = []
            self.aggregator_device_mapping[message["aggregator_uuid"]].append(
                message["device_uuid"]
            )
            self.device_aggregator_mapping[message["device_uuid"]] = message["aggregator_uuid"]
            response_message = {
                "status": "SELECTED",
                "aggregator_uuid": message["aggregator_uuid"],
                "device_uuid": message["device_uuid"],
                "transaction_id": message["transaction_id"],
            }
        elif message["device_uuid"] in self.device_aggregator_mapping:
            msg = (
                f"Device already have selected "
                f"{self.device_aggregator_mapping[message['device_uuid']]}"
            )
            response_message = {
                "status": "error",
                "aggregator_uuid": message["aggregator_uuid"],
                "device_uuid": message["device_uuid"],
                "transaction_id": message["transaction_id"],
                "msg": msg,
            }
        else:
            self.aggregator_device_mapping[message["aggregator_uuid"]].append(
                message["device_uuid"]
            )
            self.device_aggregator_mapping[message["device_uuid"]] = message["aggregator_uuid"]
            response_message = {
                "status": "SELECTED",
                "aggregator_uuid": message["aggregator_uuid"],
                "device_uuid": message["device_uuid"],
                "transaction_id": message["transaction_id"],
            }
        self.redis_db.publish(AggregatorChannels().response, json.dumps(response_message))

    def _unselect_aggregator(self, message):
        if (
            message["device_uuid"] in self.device_aggregator_mapping
            and message["aggregator_uuid"] in self.aggregator_device_mapping
        ):
            try:
                with self.lock:
                    del self.device_aggregator_mapping[message["device_uuid"]]
                    self.aggregator_device_mapping[message["aggregator_uuid"]].remove(
                        message["device_uuid"]
                    )
                response_message = {
                    "status": "UNSELECTED",
                    "aggregator_uuid": message["aggregator_uuid"],
                    "device_uuid": message["device_uuid"],
                    "transaction_id": message["transaction_id"],
                }
                self.redis_db.publish(AggregatorChannels().response, json.dumps(response_message))
            except Exception as e:  # pylint: disable=broad-except
                response_message = {
                    "status": "error",
                    "aggregator_uuid": message["aggregator_uuid"],
                    "device_uuid": message["device_uuid"],
                    "transaction_id": message["transaction_id"],
                    "msg": f"Error unselecting aggregator : {e}",
                }
            self.redis_db.publish(AggregatorChannels().response, json.dumps(response_message))

    def _create_aggregator(self, message):
        if message["transaction_id"] not in self.aggregator_device_mapping:
            with self.lock:
                self.aggregator_device_mapping[message["transaction_id"]] = []
            success_response_message = {
                "status": "ready",
                "name": message["name"],
                "transaction_id": message["transaction_id"],
            }
            self.redis_db.publish(
                AggregatorChannels().response, json.dumps(success_response_message)
            )

        else:
            error_response_message = {
                "status": "error",
                "aggregator_uuid": message["transaction_id"],
                "transaction_id": message["transaction_id"],
            }
            self.redis_db.publish(
                AggregatorChannels().response, json.dumps(error_response_message)
            )

    def _delete_aggregator(self, message):
        if message["aggregator_uuid"] in self.aggregator_device_mapping:
            del self.aggregator_device_mapping[message["aggregator_uuid"]]
            success_response_message = {
                "status": "deleted",
                "aggregator_uuid": message["aggregator_uuid"],
                "transaction_id": message["transaction_id"],
            }
            self.redis_db.publish(
                AggregatorChannels().response, json.dumps(success_response_message)
            )
        else:
            error_response_message = {
                "status": "error",
                "aggregator_uuid": message["aggregator_uuid"],
                "transaction_id": message["transaction_id"],
            }
            self.redis_db.publish(
                AggregatorChannels().response, json.dumps(error_response_message)
            )

    def receive_batch_commands_callback(self, payload):
        """Buffer the received batch commands."""
        batch_command_message = json.loads(payload["data"])
        transaction_id = batch_command_message["transaction_id"]
        with self.lock:
            self.pending_batch_commands[transaction_id] = {
                "aggregator_uuid": batch_command_message["aggregator_uuid"],
                "batch_commands": batch_command_message["batch_commands"],
            }

    def approve_batch_commands(self):
        """Moves all batch commands over from the pending buffer to be processed in
        consume_all_area_commands"""
        with self.lock:
            self.processing_batch_commands = self.pending_batch_commands
            self.pending_batch_commands = {}

    def consume_all_area_commands(self, area_uuid: str, strategy_method):
        """Processing all batch commands and collecting and sending responses."""
        for transaction_id, command_to_process in self.processing_batch_commands.items():
            if "aggregator_uuid" not in command_to_process:
                logging.error(
                    "Aggregator uuid parameter missing from transaction with "
                    "id %s. Full command %s.",
                    transaction_id,
                    command_to_process,
                )
                continue
            aggregator_uuid = command_to_process["aggregator_uuid"]
            area_commands = command_to_process["batch_commands"].pop(area_uuid, None)
            if area_commands is None:
                continue

            response = [
                strategy_method({**command, "transaction_id": transaction_id})
                for command in area_commands
            ]
            if transaction_id not in self.responses_batch_commands:
                self.responses_batch_commands[transaction_id] = {aggregator_uuid: {}}
            if area_uuid not in self.responses_batch_commands[transaction_id][aggregator_uuid]:
                self.responses_batch_commands[transaction_id][aggregator_uuid].update(
                    {area_uuid: []}
                )
            self.responses_batch_commands[transaction_id][aggregator_uuid][area_uuid].extend(
                response
            )

    @staticmethod
    def _publish_all_events_from_one_type(redis, event_dict: dict, event_type: str):
        """Reading from the event buffers and publishing all events of one type to the clients
        Args:
            redis: ExternalConnectionCommunicator
            event_dict:
            event_type:

        Returns:
        """
        for aggregator_uuid, event in event_dict.items():
            publish_event_dict = {
                **event,
                "event": event_type,
                "simulation_id": (
                    gsy_e.constants.CONFIGURATION_ID
                    if gsy_e.constants.EXTERNAL_CONNECTION_WEB
                    else None
                ),
            }
            if ConstSettings.MASettings.MARKET_TYPE != SpotMarketTypeEnum.COEFFICIENTS.value:
                publish_event_dict["num_ticks"] = (
                    100 / gsy_e.constants.DISPATCH_EVENT_TICK_FREQUENCY_PERCENT
                )
            redis.publish_json(
                AggregatorChannels(gsy_e.constants.CONFIGURATION_ID, aggregator_uuid).events,
                publish_event_dict,
            )

        event_dict.clear()

    def publish_all_events(self, redis):
        """Wrapper for _publish_all_events_from_one_type for all event types
        Args:
            redis: ExternalConnectionCommunicator

        Returns:

        """
        print(self.batch_market_cycle_events)
        self._publish_all_events_from_one_type(redis, self.batch_market_cycle_events, "market")
        self._publish_all_events_from_one_type(redis, self.batch_tick_events, "tick")
        self._publish_all_events_from_one_type(redis, self.batch_finished_events, "finish")
        self._publish_all_events_from_one_type(redis, self.batch_trade_events, "trade")

    def publish_all_commands_responses(self, redis):
        """Sending batch commands responses that were buffered in self.responses_batch_commands
        via redis to the client"""
        for transaction_id, batch_commands in self.responses_batch_commands.items():
            for aggregator_uuid, response_body in batch_commands.items():
                redis.publish_json(
                    AggregatorChannels(
                        gsy_e.constants.CONFIGURATION_ID, aggregator_uuid
                    ).batch_commands_response,
                    {
                        "command": "batch_commands",
                        "transaction_id": transaction_id,
                        "aggregator_uuid": aggregator_uuid,
                        "responses": response_body,
                    },
                )

        self.responses_batch_commands = {}
        self.processing_batch_commands = {}
