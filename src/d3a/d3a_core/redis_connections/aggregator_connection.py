import json
import logging
from copy import deepcopy
from threading import Lock
import d3a.constants
from d3a_interface.utils import create_subdict_or_update
from d3a.d3a_core.singletons import external_global_statistics


class AggregatorHandler:

    def __init__(self, redis_db):
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
        self.aggregator_device_mapping = aggregator_device
        self.device_aggregator_mapping = {
            dev: aggr
            for aggr, devices in self.aggregator_device_mapping.items()
            for dev in devices
        }

    def is_controlling_device(self, device_uuid):
        return device_uuid in self.device_aggregator_mapping

    def _add_batch_event(self, device_uuid, event, batch_event_dict):
        aggregator_uuid = self.device_aggregator_mapping[device_uuid]
        create_subdict_or_update(batch_event_dict, aggregator_uuid, event)

    def _delete_not_owned_devices_from_dict(self, area_stats_tree_dict):
        out_dict = deepcopy(area_stats_tree_dict)
        self._delete_not_owned_devices(area_stats_tree_dict, out_dict)
        return out_dict

    def _delete_not_owned_devices(self, indict, outdict):
        for area_uuid, area_dict in indict.items():
            if 'children' in area_dict:
                self._delete_not_owned_devices(indict[area_uuid]['children'],
                                               outdict[area_uuid]['children'])
            else:
                if area_uuid not in self.device_aggregator_mapping:
                    outdict[area_uuid] = {}

    def add_batch_market_event(self, device_uuid, market_info):
        market_info.update({'grid_tree': self._delete_not_owned_devices_from_dict(
            external_global_statistics.area_stats_tree_dict)})
        self._add_batch_event(device_uuid, market_info, self.batch_market_cycle_events)

    def add_batch_tick_event(self, device_uuid, tick_info):
        tick_info.update({'grid_tree': self._delete_not_owned_devices_from_dict(
            external_global_statistics.area_stats_tree_dict)})
        self._add_batch_event(device_uuid, tick_info, self.batch_tick_events)

    def add_batch_finished_event(self, device_uuid, finish_info):
        self._add_batch_event(device_uuid, finish_info, self.batch_finished_events)

    def add_batch_trade_event(self, device_uuid, trade_info):
        aggregator_uuid = self.device_aggregator_mapping[device_uuid]
        if aggregator_uuid not in self.batch_trade_events:
            self.batch_trade_events[aggregator_uuid] = \
                {'grid_tree': {},
                 'trade_list': []}

        self.batch_trade_events[aggregator_uuid]["grid_tree"] = \
            self._delete_not_owned_devices_from_dict(
                external_global_statistics.area_stats_tree_dict)
        self.batch_trade_events[aggregator_uuid]["trade_list"].append(trade_info)

    def aggregator_callback(self, payload):
        message = json.loads(payload["data"])
        if d3a.constants.EXTERNAL_CONNECTION_WEB is True and \
                message['config_uuid'] != d3a.constants.COLLABORATION_ID:
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
        if message['aggregator_uuid'] not in self.aggregator_device_mapping:
            self.aggregator_device_mapping[message['aggregator_uuid']] = []
            self.aggregator_device_mapping[message['aggregator_uuid']].\
                append(message['device_uuid'])
            self.device_aggregator_mapping[message['device_uuid']] = message['aggregator_uuid']
            response_message = {
                "status": "SELECTED", "aggregator_uuid": message['aggregator_uuid'],
                "device_uuid": message['device_uuid'],
                "transaction_id": message['transaction_id']}
        elif message['device_uuid'] in self.device_aggregator_mapping:
            msg = f"Device already have selected " \
                  f"{self.device_aggregator_mapping[message['device_uuid']]}"
            response_message = {
                "status": "error", "aggregator_uuid": message['aggregator_uuid'],
                "device_uuid": message['device_uuid'],
                "transaction_id": message['transaction_id'],
                "msg": msg
            }
        else:
            self.aggregator_device_mapping[message['aggregator_uuid']].\
                append(message['device_uuid'])
            self.device_aggregator_mapping[message['device_uuid']] = message['aggregator_uuid']
            response_message = {
                "status": "SELECTED", "aggregator_uuid": message['aggregator_uuid'],
                "device_uuid": message['device_uuid'],
                "transaction_id": message['transaction_id']}
        self.redis_db.publish(
            "aggregator_response", json.dumps(response_message)
        )

    def _unselect_aggregator(self, message):
        if message['device_uuid'] in self.device_aggregator_mapping and \
                message['aggregator_uuid'] in self.aggregator_device_mapping:
            try:
                with self.lock:
                    del self.device_aggregator_mapping[message['device_uuid']]
                    self.aggregator_device_mapping[message['aggregator_uuid']]\
                        .remove(message['device_uuid'])
                response_message = {
                    "status": "UNSELECTED", "aggregator_uuid": message['aggregator_uuid'],
                    "device_uuid": message['device_uuid'],
                    "transaction_id": message['transaction_id']}
                self.redis_db.publish(
                    "aggregator_response", json.dumps(response_message)
                )
            except Exception as e:
                response_message = {
                    "status": "error", "aggregator_uuid": message['aggregator_uuid'],
                    "device_uuid": message['device_uuid'],
                    "transaction_id": message['transaction_id'],
                    "msg": f"Error unselecting aggregator : {e}"
                }
            self.redis_db.publish(
                "aggregator_response", json.dumps(response_message)
            )

    def _create_aggregator(self, message):
        if message['transaction_id'] not in self.aggregator_device_mapping:
            with self.lock:
                self.aggregator_device_mapping[message['transaction_id']] = []
            success_response_message = {
                "status": "ready", "name": message['name'],
                "transaction_id": message['transaction_id']}
            self.redis_db.publish(
                "aggregator_response", json.dumps(success_response_message)
            )

        else:
            error_response_message = {
                "status": "error", "aggregator_uuid": message['transaction_id'],
                "transaction_id": message['transaction_id']}
            self.redis_db.publish(
                "aggregator_response", json.dumps(error_response_message)
            )

    def _delete_aggregator(self, message):
        if message['aggregator_uuid'] in self.aggregator_device_mapping:
            del self.aggregator_device_mapping[message['aggregator_uuid']]
            success_response_message = {
                "status": "deleted", "aggregator_uuid": message['aggregator_uuid'],
                "transaction_id": message['transaction_id']}
            self.redis_db.publish(
                "aggregator_response", json.dumps(success_response_message)
            )
        else:
            error_response_message = {
                "status": "error", "aggregator_uuid": message['aggregator_uuid'],
                "transaction_id": message['transaction_id']}
            self.redis_db.publish(
                "aggregator_response", json.dumps(error_response_message)
            )

    def receive_batch_commands_callback(self, payload):
        batch_command_message = json.loads(payload["data"])
        transaction_id = batch_command_message["transaction_id"]
        with self.lock:
            self.pending_batch_commands[transaction_id] = {
                "aggregator_uuid": batch_command_message["aggregator_uuid"],
                "batch_commands": batch_command_message["batch_commands"]
            }

    def approve_batch_commands(self):
        with self.lock:
            self.processing_batch_commands = self.pending_batch_commands
            self.pending_batch_commands = {}

    def consume_all_area_commands(self, area_uuid, strategy_method):
        for transaction_id, command_to_process in self.processing_batch_commands.items():
            if "aggregator_uuid" not in command_to_process:
                logging.error(f"Aggregator uuid parameter missing from transaction with "
                              f"id {transaction_id}. Full command {command_to_process}.")
                continue
            aggregator_uuid = command_to_process["aggregator_uuid"]
            area_commands = command_to_process["batch_commands"].pop(area_uuid, None)
            if area_commands is None:
                continue

            response = [strategy_method({**command, 'transaction_id': transaction_id})
                        for command in area_commands]
            if transaction_id not in self.responses_batch_commands:
                self.responses_batch_commands[transaction_id] = {aggregator_uuid: []}
            self.responses_batch_commands[transaction_id][aggregator_uuid].append(response)

    def _publish_all_events_from_one_type(self, redis, event_dict, event_type):
        for aggregator_uuid, event in event_dict.items():
            event_channel = f"external-aggregator/{d3a.constants.COLLABORATION_ID}/" \
                            f"{aggregator_uuid}/events/all"

            publish_event_dict = {**event,
                                  'event': event_type,
                                  'num_ticks': 100 /
                                  d3a.constants.DISPATCH_EVENT_TICK_FREQUENCY_PERCENT,
                                  'simulation_id': d3a.constants.COLLABORATION_ID if
                                  d3a.constants.EXTERNAL_CONNECTION_WEB else None
                                  }
            redis.publish_json(event_channel, publish_event_dict)

        event_dict.clear()

    def publish_all_events(self, redis):
        self._publish_all_events_from_one_type(redis, self.batch_market_cycle_events, "market")
        self._publish_all_events_from_one_type(redis, self.batch_tick_events, "tick")
        self._publish_all_events_from_one_type(redis, self.batch_finished_events, "finish")
        self._publish_all_events_from_one_type(redis, self.batch_trade_events, "trade")

    def publish_all_commands_responses(self, redis):
        for transaction_id, batch_commands in self.responses_batch_commands.items():
            for aggregator_uuid, response_body in batch_commands.items():
                redis.publish_json(
                    f"external-aggregator/{d3a.constants.COLLABORATION_ID}/"
                    f"{aggregator_uuid}/response/batch_commands",
                    {
                        "command": "batch_commands",
                        "transaction_id": transaction_id,
                        "aggregator_uuid": aggregator_uuid,
                        "responses": response_body
                     }
                )

        self.responses_batch_commands = {}
        self.processing_batch_commands = {}
