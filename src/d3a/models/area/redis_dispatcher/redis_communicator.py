from redis import StrictRedis
from threading import Event
import logging
from d3a.d3a_core.redis_communication import REDIS_URL


log = logging.getLogger(__name__)


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
        self.threads = []

    def stop_all_threads(self):
        self.resume()
        for thread in self.threads:
            try:
                thread.stop()
            except Exception as e:
                logging.debug(f"Thread stop failed for thread {thread}: {e}")

        for thread in self.threads:
            try:
                thread.join(timeout=0.5)
            except Exception as e:
                logging.debug(f"Thread join failed for thread {thread}: {e}")

        try:
            self.pubsub.close()
            self.pubsub_response.close()
        except Exception as e:
            logging.debug(f"Error when closing pubsub connection: {e}")

        self.threads = []

    def sub_to_multiple_channels(self, channel_callback_dict):
        self.pubsub.subscribe(**channel_callback_dict)
        thread = self.pubsub.run_in_thread(daemon=True)
        log.trace(f"Started thread for multiple channels: {thread}")
        self.threads.append(thread)

    def sub_to_response(self, channel, callback):
        thread = super().sub_to_response(channel, callback)
        self.threads.append(thread)

    def unsubscribe_from_all(self):
        self.pubsub.unsubscribe()
        self.pubsub_response.unsubscribe()

    def reset_connection(self):
        self.pubsub.reset()
        self.pubsub_response.reset()
