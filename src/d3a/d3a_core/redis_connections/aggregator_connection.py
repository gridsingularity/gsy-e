import json
import logging
from threading import Lock
import d3a.constants


class AggregatorHandler:

    def __init__(self):
        self.pending_batch_commands = {}
        self.processing_batch_commands = {}
        self.responses_batch_commands = {}
        self.batch_events = {}
        self.aggregator_device_mapping = {}
        self.device_aggregator_mapping = {}
        self.lock = Lock()

    def set_aggregator_device_mapping(self, aggregator_device):
        self.aggregator_device_mapping = aggregator_device
        self.device_aggregator_mapping = {
            dev: aggr
            for aggr, devices in self.aggregator_device_mapping
            for dev in devices
        }

    def is_controlling_device(self, device_uuid):
        return device_uuid in self.device_aggregator_mapping

    def add_batch_event(self, device_uuid, event):
        aggregator_uuid = self.device_aggregator_mapping[device_uuid]

        if aggregator_uuid not in self.batch_events:
            self.batch_events[aggregator_uuid] = []

        self.batch_events[aggregator_uuid].append(event)

    def receive_batch_commands_callback(self, payload):
        batch_command_message = json.loads(payload["data"])
        transaction_id = batch_command_message["transaction_id"]
        with self.lock:
            self.pending_batch_commands[transaction_id] = batch_command_message

    def approve_batch_commands(self):
        with self.lock:
            self.processing_batch_commands = self.pending_batch_commands
            self.pending_batch_commands = {}

    def consume_all_area_commands(self, area_uuid, strategy_method):
        for transaction_id, command_to_process in self.processing_batch_commands.values():
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

    def publish_all_events(self, redis):
        for aggregator_uuid, event_list in self.batch_events.items():
            redis.publish_json(
                f"external-aggregator/{d3a.constants.COLLABORATION_ID}/{aggregator_uuid}/events",
                event_list
            )
        self.batch_events = {}

    def publish_all_commands_responses(self, redis):
        for transaction_id, batch_commands in self.responses_batch_commands.items():
            aggregator_uuid = batch_commands[0]
            response_body = batch_commands[1]
            redis.publish_json(
                f"external-aggregator/{d3a.constants.COLLABORATION_ID}/"
                f"{aggregator_uuid}/response/batch_commands",
                {
                    "transaction_id": transaction_id,
                    "aggregator_uuid": aggregator_uuid,
                    "responses": response_body
                 }
            )
        self.responses_batch_commands = {}
