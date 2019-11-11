from redis import StrictRedis
from threading import Event
from d3a.d3a_core.redis_communication import REDIS_URL


class RedisAreaCommunicator:
    def __init__(self):
        self.redis_db = StrictRedis.from_url(REDIS_URL)
        self.pubsub = self.redis_db.pubsub()
        self.pubsub_response = self.redis_db.pubsub()
        self.area_event = Event()
        self.threads = []

    def stop_all_threads(self):
        try:
            self.pubsub.unsubscribe()
            self.pubsub_response.unsubscribe()
        except Exception as e:
            print(f"Exception when unsubscribing from all channels {e}")

        for thread in self.threads:
            print(f"STOPPING THREAD {thread}")
            try:
                thread.stop()
            except Exception as e:
                print(f"THREAD STOP FAILED {e}")

        for thread in self.threads:
            print(f"JOIN THREAD {thread}")
            thread.join()
            print(f"THREAD JOINED {thread}")

        try:
            self.pubsub.close()
            self.pubsub_response.close()
        except Exception as e:
            print(f"Exception when closing the pubsub connections {e}")

        self.threads = []

    def reset_connection(self):
        self.stop_all_threads()
        print("AFTER STOP ALL THREADS")
        # self.redis_db = StrictRedis.from_url(REDIS_URL)
        self.pubsub = self.redis_db.pubsub()
        print("RECREATED PUBSUB")
        self.pubsub_response = self.redis_db.pubsub()

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
        print(f"STARTING RESPONSE THREAD {thread}")
        self.threads.append(thread)

    def sub_to_area_event(self, channel, callback):
        self.pubsub.subscribe(**{channel: callback})
        thread = self.pubsub.run_in_thread(daemon=True)
        print(f"STARTING AREA THREAD {thread}")
        self.threads.append(thread)

    def sub_to_multiple_channels(self, channel_callback_dict):
        self.pubsub.subscribe(**channel_callback_dict)
        thread = self.pubsub.run_in_thread(daemon=True)
        print(f"STARTING MULTI THREAD {thread}")
        self.threads.append(thread)
