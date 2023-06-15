"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
from collections.abc import Callable
from threading import Event, Lock, Thread
from time import time
from typing import Dict

from gsy_framework.redis_channels import QueueNames, AggregatorChannels
from redis import Redis
from rq import Queue

import gsy_e.constants
from gsy_e.constants import REDIS_PUBLISH_RESPONSE_TIMEOUT
from gsy_e.gsy_e_core.redis_connections.aggregator import AggregatorHandler
from gsy_e.gsy_e_core.redis_connections.simulation import REDIS_URL

log = logging.getLogger(__name__)
REDIS_THREAD_JOIN_TIMEOUT = 2
REDIS_POLL_TIMEOUT = 0.01


class RedisCommunicator:
    """Base class for redis communication using pubsub."""

    def __init__(self):
        self.redis_db = Redis.from_url(REDIS_URL, retry_on_timeout=True)
        self.pubsub = self.redis_db.pubsub()
        self.pubsub_response = self.redis_db.pubsub()
        self.event = Event()

    def publish(self, channel: str, data: str):
        """Publish message on redis channel."""
        self.redis_db.publish(channel, data)

    def wait(self):
        """Wait for thread event to be performed."""
        self.event.wait()
        self.event.clear()

    def resume(self):
        """Resume receiving events."""
        self.event.set()

    def sub_to_response(self, channel: str, callback: Callable) -> Thread:
        """Subscribe to response channel and return pubsub thread."""
        self.pubsub_response.subscribe(**{channel: callback})
        thread = self.pubsub_response.run_in_thread(daemon=True)
        log.trace(f"Started thread for responses: {thread}")
        return thread

    def sub_to_channel(self, channel: str, callback: Callable) -> Thread:
        """Subscribe to channel and return pubsub thread."""
        self.pubsub.subscribe(**{channel: callback})
        thread = self.pubsub.run_in_thread(daemon=True)
        log.trace(f"Started thread for events: {thread}")
        return thread


class BlockingCommunicator(RedisCommunicator):
    """Communicator for sending blocking messages via redis pubsub."""

    def __init__(self):
        super().__init__()
        self.lock = Lock()

    def sub_to_channel(self, channel: str, callback: Callable):
        """Subscribe to channel."""
        self.pubsub.subscribe(**{channel: callback})

    def poll_until_response_received(self, response_received_callback: Callable):
        """Wait until response of send message was received."""
        start_time = time()
        while not response_received_callback() and \
                (time() - start_time < REDIS_PUBLISH_RESPONSE_TIMEOUT):
            with self.lock:
                self.pubsub.get_message(timeout=REDIS_POLL_TIMEOUT)


class ResettableCommunicator(RedisCommunicator):
    """
    Communicator for sending messages adn receiving their responses using redis pubsub
    that runs in a thread which can be restarted.
    """

    def __init__(self):
        super().__init__()
        self.thread = None

    def terminate_connection(self):
        """Terminate connection to redis pubsub."""
        try:
            self.thread.stop()
            self.thread.join(timeout=REDIS_THREAD_JOIN_TIMEOUT)
            self.pubsub.close()
            self.thread = None
        # pylint: disable=broad-except
        except Exception as ex:
            logging.debug("Error when stopping all threads: %s", ex)

    def sub_to_multiple_channels(self, channel_callback_dict: Dict):
        """Subscribe to multiple redis channels."""
        assert self.thread is None, \
            f"There has to be only one thread per ResettableCommunicator object, " \
            f" thread {self.thread} already exists."
        self.pubsub.subscribe(**channel_callback_dict)
        thread = self.pubsub.run_in_thread(sleep_time=0.1, daemon=True)
        log.debug("Started ResettableCommunicator thread for multiple channels: %s", thread)
        self.thread = thread

    def sub_to_response(self, channel: str, callback: Callable):
        assert self.thread is None, \
            f"There has to be only one thread per ResettableCommunicator object, " \
            f" thread {self.thread} already exists."
        thread = super().sub_to_response(channel, callback)
        self.thread = thread

    def publish_json(self, channel: str, data: Dict):
        """Publish json serializable dict to redis channel."""
        self.publish(channel, json.dumps(data))


class RQResettableCommunicator(ResettableCommunicator):
    """Communicator for sending messages using redis queue."""

    def publish_json(self, channel: str, data: Dict) -> None:
        """Publish json serializable dict to redis queue."""
        queue = Queue(QueueNames().sdk_communication, connection=self.redis_db)
        queue.enqueue(channel, json.dumps(data))


class ExternalConnectionCommunicator(ResettableCommunicator):
    """Communicator for sending messages using redis pubsub including utils for aggregator."""

    def __init__(self, is_enabled):
        self.is_enabled = is_enabled
        self.aggregator = None
        if self.is_enabled:
            super().__init__()
            self.channel_callback_dict = {}
            self.aggregator = AggregatorHandler(self.redis_db)

    def activate(self):
        """Connect to aggregator.
        Two stage init is needed here because redis might not be initiated at this point"""
        self.sub_to_aggregator()
        self.start_communication()

    def sub_to_channel(self, channel: str, callback: Callable):
        if not self.is_enabled:
            return
        self.pubsub.subscribe(**{channel: callback})

    def sub_to_multiple_channels(self, channel_callback_dict: Dict):
        if not self.is_enabled:
            return
        self.pubsub.subscribe(**channel_callback_dict)

    def start_communication(self):
        """Start pubsub thread."""
        if not self.is_enabled:
            return
        if not self.pubsub.subscribed:
            return
        thread = self.pubsub.run_in_thread(sleep_time=0.1, daemon=True)
        log.debug("Started ExternalConnectionCommunicator thread for multiple channels: %s",
                  thread)
        self.thread = thread

    def sub_to_aggregator(self):
        """Subscribe to aggregator channels."""
        if not self.is_enabled:
            return
        channel_names = AggregatorChannels(gsy_e.constants.CONFIGURATION_ID, "")
        channel_callback_dict = {
            channel_names.batch_commands: self.aggregator.receive_batch_commands_callback,
            channel_names.commands: self.aggregator.aggregator_callback
        }
        self.pubsub.psubscribe(**channel_callback_dict)

    def approve_aggregator_commands(self):
        """Wrapper for calling approve_batch_commands."""
        if not self.is_enabled:
            return
        self.aggregator.approve_batch_commands()

    def publish_aggregator_commands_responses_events(self):
        """Wrapper for publishing aggregator command responses and events."""
        if not self.is_enabled:
            return
        self.aggregator.publish_all_commands_responses(self)
        self.aggregator.publish_all_events(self)


class RQExternalConnectionCommunicator(ExternalConnectionCommunicator, RQResettableCommunicator):
    """Communicator for sending messages using redis queue including utils for aggregator."""


def external_redis_communicator_factory(is_enabled: bool) -> ExternalConnectionCommunicator:
    """Return either a rq or pubsub based external communicator including aggregator utils."""
    return (RQExternalConnectionCommunicator(is_enabled)
            if gsy_e.constants.SEND_EVENTS_RESPONSES_TO_SDK_VIA_RQ
            else ExternalConnectionCommunicator(is_enabled))


def matching_engine_redis_communicator_factory() -> ResettableCommunicator:
    """Return either a rq or pubsub based external communicator."""
    return (RQResettableCommunicator()
            if gsy_e.constants.SEND_EVENTS_RESPONSES_TO_SDK_VIA_RQ else ResettableCommunicator())
