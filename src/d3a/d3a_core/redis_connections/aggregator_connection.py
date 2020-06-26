import json
import logging
from threading import Lock
import d3a.constants
from redis import StrictRedis
from d3a.d3a_core.redis_connections.redis_communication import REDIS_URL


class AggregatorHandler:

    def __init__(self):
        self.redis_db = StrictRedis.from_url(REDIS_URL, retry_on_timeout=True)
        self.pubsub = self.redis_db.pubsub()
        self.pending_batch_commands = {}
        self.processing_batch_commands = {}
        self.responses_batch_commands = {}
        self.batch_market_cycle_events = {}
        self.batch_tick_events = {}
        self.batch_trade_events = {}
        self.batch_finished_events = {}
        self.selected_aggregators = []
        self.aggregator_device_mapping = {}
        self.device_aggregator_mapping = {}
        self.lock = Lock()

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

        if aggregator_uuid not in batch_event_dict:
            batch_event_dict[aggregator_uuid] = []

        batch_event_dict[aggregator_uuid].append(event)

    def add_batch_market_event(self, device_uuid, event):
        self._add_batch_event(device_uuid, event, self.batch_market_cycle_events)

    def add_batch_tick_event(self, device_uuid, event):
        self._add_batch_event(device_uuid, event, self.batch_tick_events)

    def add_batch_trade_event(self, device_uuid, event):
        self._add_batch_event(device_uuid, event, self.batch_trade_events)

    def add_batch_finished_event(self, device_uuid, event):
        self._add_batch_event(device_uuid, event, self.batch_finished_events)

    def crud_aggregator_callback(self, payload):
        print(f"payload: {payload}")
        message = json.loads(payload["data"])
        transaction_id = message["transaction_id"]
        if message["type"] == "CREATE":
            self._create_aggregator(message, transaction_id)
        elif message["type"] == "DELETE":
            self._delete_aggregator(message, transaction_id)
        elif message["type"] == "SELECT":
            self._select_aggregator(message, transaction_id)

    def _select_aggregator(self, message, transaction_id):
        self.aggregator_device_mapping = {}
        self.device_aggregator_mapping = {}

        if message['aggregator_name'] not in self.selected_aggregators:
            self.aggregator_device_mapping[message['aggregator_name']] = []
            msg = f"{self.device_aggregator_mapping[message['device_name']]} " \
                  f"aggregator not found."
            error_response_message = {
                "status": "error", "aggregator_name": message['aggregator_name'],
                "device_name": message['device_name'],
                "transaction_id": transaction_id,
                "msg": msg
            }
            self.redis_db.publish(
                "crud_aggregator_response", json.dumps(error_response_message)
            )
        elif message['device_name'] in self.device_aggregator_mapping:
            msg = f"Device already have selected " \
                  f"{self.device_aggregator_mapping[message['device_name']]}"
            error_response_message = {
                "status": "error", "aggregator_name": message['aggregator_name'],
                "device_name": message['device_name'],
                "transaction_id": transaction_id,
                "msg": msg
            }
            self.redis_db.publish(
                "crud_aggregator_response", json.dumps(error_response_message)
            )
        else:
            self.aggregator_device_mapping[message['aggregator_name']].\
                append(message['device_name'])
            self.device_aggregator_mapping[message['device_name']] = message['aggregator_name']
            success_response_message = {
                "status": "ready", "aggregator_name": message['aggregator_name'],
                "device_name": message['device_name'],
                "transaction_id": transaction_id}
            self.redis_db.publish(
                "crud_aggregator_response", json.dumps(success_response_message)
            )

    def _create_aggregator(self, message, transaction_id):
        if message['name'] not in self.selected_aggregators:
            self.selected_aggregators.append(message['name'])
            print(f"selected_aggregators: {self.selected_aggregators}")
            success_response_message = {
                "status": "ready", "name": message['name'],
                "transaction_id": transaction_id}
            self.redis_db.publish(
                "crud_aggregator_response", json.dumps(success_response_message)
            )
        else:
            print(f"doublecount")
            error_response_message = {
                "status": "error", "name": message['name'],
                "transaction_id": transaction_id}
            self.redis_db.publish(
                "crud_aggregator_response", json.dumps(error_response_message)
            )

    def _delete_aggregator(self, message, transaction_id):
        if message['name'] in self.selected_aggregators:
            aggr_name = self.selected_aggregators.pop(
                self.selected_aggregators.index(message['name'])
            )
            print(f"aggr_name: {aggr_name}")
            success_response_message = {
                "status": "deleted", "name": message['name'],
                "transaction_id": transaction_id}
            self.redis_db.publish(
                "crud_aggregator_response", json.dumps(success_response_message)
            )
        else:
            print(f"doublecount")
            error_response_message = {
                "status": "error", "name": message['name'],
                "transaction_id": transaction_id}
            self.redis_db.publish(
                "crud_aggregator_response", json.dumps(error_response_message)
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
            self.responses_batch_commands[transaction_id] = (aggregator_uuid, [
                strategy_method({**command, 'transaction_id': transaction_id})
                for command in area_commands
            ])

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

    def publish_all_commands_responses(self, redis):
        for transaction_id, batch_commands in self.responses_batch_commands.items():
            aggregator_uuid = batch_commands[0]
            response_body = batch_commands[1]
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
