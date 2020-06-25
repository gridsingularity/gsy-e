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
from redis import StrictRedis
from threading import Event, Lock
import logging
import json
from time import time
from d3a.d3a_core.redis_connections.redis_communication import REDIS_URL
from d3a.constants import REDIS_PUBLISH_RESPONSE_TIMEOUT
import d3a.constants

log = logging.getLogger(__name__)
REDIS_THREAD_JOIN_TIMEOUT = 2
REDIS_POLL_TIMEOUT = 0.01


class RedisCommunicator:
    def __init__(self):
        self.redis_db = StrictRedis.from_url(REDIS_URL, retry_on_timeout=True)
        self.pubsub = self.redis_db.pubsub()
        self.pubsub_response = self.redis_db.pubsub()
        self.event = Event()

    def publish(self, channel, data):
        self.redis_db.publish(channel, data)

    def wait(self):
        self.event.wait()
        self.event.clear()

    def resume(self):
        self.event.set()

    def sub_to_response(self, channel, callback):
        self.pubsub_response.subscribe(**{channel: callback})
        thread = self.pubsub_response.run_in_thread(daemon=True)
        log.trace(f"Started thread for responses: {thread}")
        return thread

    def sub_to_channel(self, channel, callback):
        self.pubsub.subscribe(**{channel: callback})
        thread = self.pubsub.run_in_thread(daemon=True)
        log.trace(f"Started thread for events: {thread}")
        return thread


class ResettableCommunicator(RedisCommunicator):
    def __init__(self):
        super().__init__()
        self.thread = None

    def terminate_connection(self):
        try:
            self.thread.stop()
            self.thread.join(timeout=REDIS_THREAD_JOIN_TIMEOUT)
            self.pubsub.close()
            self.thread = None
        except Exception as e:
            logging.debug(f"Error when stopping all threads: {e}")

    def sub_to_multiple_channels(self, channel_callback_dict):
        assert self.thread is None, \
            f"There has to be only one thread per ResettableCommunicator object, " \
            f" thread {self.thread} already exists."
        self.pubsub.subscribe(**channel_callback_dict)
        thread = self.pubsub.run_in_thread(daemon=True)
        log.trace(f"Started thread for multiple channels: {thread}")
        self.thread = thread

    def sub_to_response(self, channel, callback):
        assert self.thread is None, \
            f"There has to be only one thread per ResettableCommunicator object, " \
            f" thread {self.thread} already exists."
        thread = super().sub_to_response(channel, callback)
        self.thread = thread

    def publish_json(self, channel, data):
        self.publish(channel, json.dumps(data))


class ExternalConnectionCommunicator(ResettableCommunicator):
    def __init__(self, is_enabled):
        self.is_enabled = is_enabled
        if self.is_enabled:
            super().__init__()
            self.channel_callback_dict = {}

    def sub_to_channel(self, channel, callback):
        if not self.is_enabled:
            return
        self.pubsub.subscribe(**{channel: callback})

    def sub_to_multiple_channels(self, channel_callback_dict):
        if not self.is_enabled:
            return
        self.pubsub.subscribe(**channel_callback_dict)

    def start_communication(self):
        if not self.is_enabled:
            return
        if not self.pubsub.channels:
            return
        thread = self.pubsub.run_in_thread(daemon=True)
        log.trace(f"Started thread for multiple channels: {thread}")
        self.thread = thread

    def sub_to_aggregator(self, aggregator):
        if not self.is_enabled:
            return
        self.pubsub.psubscribe(**{
            f'external/{d3a.constants.COLLABORATION_ID}/aggregator/*/batch_commands':
                aggregator.receive_batch_commands_callback
        })

    def approve_aggregator_commands(self, aggregator):
        if not self.is_enabled:
            return
        aggregator.approve_batch_commands()

    def publish_aggregator_commands_responses_events(self, aggregator):
        if not self.is_enabled:
            return
        aggregator.publish_all_commands_responses(self)
        aggregator.publish_all_events(self)


class BlockingCommunicator(RedisCommunicator):
    def __init__(self):
        super().__init__()
        self.lock = Lock()

    def sub_to_channel(self, channel, callback):
        self.pubsub.subscribe(**{channel: callback})

    def poll_until_response_received(self, response_received_callback):
        start_time = time()
        while not response_received_callback() and \
                (time() - start_time < REDIS_PUBLISH_RESPONSE_TIMEOUT):
            with self.lock:
                self.pubsub.get_message(timeout=REDIS_POLL_TIMEOUT)
