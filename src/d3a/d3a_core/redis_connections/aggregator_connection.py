import json
import logging
from threading import Lock
from copy import deepcopy
import d3a.constants


default_market_info = {"device_info": None,
                       "device_bill": None,
                       "event": None,
                       "grid_stats_tree": None,
                       "area_uuid": None}


class AggregatorHandler:

    def __init__(self, redis_db):
        self.redis_db = redis_db
        self.pubsub = self.redis_db.pubsub()
        self.pending_batch_commands = {}
        self.processing_batch_commands = {}
        self.responses_batch_commands = {}
        self.batch_market_cycle_events = {}
        self.already_sent_grid_stats = False
        self.batch_tick_events = {}
        self.batch_trade_events = {}
        self.batch_finished_events = {}
        self.aggregator_device_mapping = {}
        self.device_aggregator_mapping = {}
        self.lock = Lock()
        self.grid_buffer = {}

    def set_aggregator_device_mapping(self, aggregator_device_mapping):
        self.aggregator_device_mapping = aggregator_device_mapping
        self.device_aggregator_mapping = {
            dev: aggr
            for aggr, devices in self.aggregator_device_mapping.items()
            for dev in devices
        }

    def is_controlling_device(self, device_uuid):
        return device_uuid in self.device_aggregator_mapping

    def _add_batch_event(self, device_uuid, event, batch_event_dict):
        aggregator_uuid = self.device_aggregator_mapping[device_uuid]

        if aggregator_uuid not in batch_event_dict:
            batch_event_dict[aggregator_uuid] = []

        batch_event_dict[aggregator_uuid].append(event)

    def _add_grid_stats_to_market_event(self, device_uuid, global_objects):
        market_info = deepcopy(default_market_info)
        market_info["grid_stats_tree"] = global_objects.area_tree_dict
        market_info["event"] = "grid_stats"
        self._add_batch_event(device_uuid, market_info, self.batch_market_cycle_events)
        self.already_sent_grid_stats = True

    def add_batch_market_event(self, device_uuid, event, global_objects):
        if not self.already_sent_grid_stats and global_objects.area_tree_dict:
            self._add_grid_stats_to_market_event(device_uuid, global_objects)
        self._add_batch_event(device_uuid, event, self.batch_market_cycle_events)

    def add_batch_tick_event(self, device_uuid, event):
        self._add_batch_event(device_uuid, event, self.batch_tick_events)

    def add_batch_trade_event(self, device_uuid, event):
        self._add_batch_event(device_uuid, event, self.batch_trade_events)

    def add_batch_finished_event(self, device_uuid, event):
        self._add_batch_event(device_uuid, event, self.batch_finished_events)

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
        for aggregator_uuid, event_list in event_dict.items():
            event_channel = f"external-aggregator/{d3a.constants.COLLABORATION_ID}/" \
                            f"{aggregator_uuid}/events/all"
            redis.publish_json(
                event_channel,
                {"event": event_type, "content": event_list}
            )
        event_dict.clear()

    def publish_all_events(self, redis):
        self._publish_all_events_from_one_type(redis, self.batch_market_cycle_events, "market")
        self._publish_all_events_from_one_type(redis, self.batch_tick_events, "tick")
        self._publish_all_events_from_one_type(redis, self.batch_trade_events, "trade")
        self._publish_all_events_from_one_type(redis, self.batch_finished_events, "finish")
        self.already_sent_grid_stats = False

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
