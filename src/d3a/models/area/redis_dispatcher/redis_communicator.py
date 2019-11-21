from redis import StrictRedis
from threading import Event, Lock
import logging
from time import time
from d3a.d3a_core.redis_communication import REDIS_URL
from d3a.constants import REDIS_PUBLISH_RESPONSE_TIMEOUT

log = logging.getLogger(__name__)
REDIS_THREAD_JOIN_TIMEOUT = 2
REDIS_POLL_TIMEOUT = 0.01


class RedisAreaCommunicator:
    def __init__(self):
        self.redis_db = StrictRedis.from_url(REDIS_URL)
        self.pubsub = self.redis_db.pubsub()
        self.pubsub_response = self.redis_db.pubsub()
        self.area_event = Event()

    def publish(self, channel, data):
        self.redis_db.publish(channel, data)

    def wait(self):
        self.area_event.wait()
        self.area_event.clear()

    def resume(self):
        self.area_event.set()

    def sub_to_response(self, channel, callback):
        self.pubsub_response.subscribe(**{channel: callback})
        thread = self.pubsub_response.run_in_thread(daemon=True)
        log.trace(f"Started thread for responses: {thread}")
        return thread

    def sub_to_area_event(self, channel, callback):
        self.pubsub.subscribe(**{channel: callback})
        thread = self.pubsub.run_in_thread(daemon=True)
        log.trace(f"Started thread for events: {thread}")
        return thread


class ResettableCommunicator(RedisAreaCommunicator):
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


class BlockingCommunicator(RedisAreaCommunicator):
    def __init__(self):
        super().__init__()
        self.lock = Lock()

    def sub_to_area_event(self, channel, callback):
        self.pubsub.subscribe(**{channel: callback})

    def poll_until_response_received(self, response_received_callback):
        start_time = time()
        while not response_received_callback() and \
                (time() - start_time < REDIS_PUBLISH_RESPONSE_TIMEOUT):
            with self.lock:
                self.pubsub.get_message(timeout=REDIS_POLL_TIMEOUT)
