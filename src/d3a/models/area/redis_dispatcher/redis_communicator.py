from redis import StrictRedis
from threading import Event
from d3a.d3a_core.redis_communication import REDIS_URL


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
        self.pubsub_response.run_in_thread(daemon=True)

    def sub_to_area_event(self, channel, callback):
        self.pubsub.subscribe(**{channel: callback})
        self.pubsub.run_in_thread(daemon=True)
