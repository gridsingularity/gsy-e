from redis import StrictRedis
import json
from d3a.d3a_core.redis_connections.redis_communication import REDIS_URL
from d3a.models.strategy.external_strategy import ExternalStrategy


class RedisAreaExternalConnection:
    def __init__(self, area):
        self.area = area
        self.redis_db = StrictRedis.from_url(REDIS_URL, retry_on_timeout=True)
        self.pubsub = self.redis_db.pubsub()
        self.sub_to_area_event()
        self.areas_to_register = []
        self.areas_to_unregister = []

    def market_cycle_event(self):
        self.unregister_pending_areas()
        self.register_new_areas()

    def unregister_pending_areas(self):
        if not self.areas_to_unregister:
            return

        for area in self.areas_to_unregister:
            try:
                area_object = next(child for child in self.area.children if child.name == area)
                area_object.deactivate()
                self.area.children.remove(area_object)
            except Exception as e:
                self.area.log.error(f"Unsubscribing of area {area} failed with error {str(e)}.")
                self.publish(f"{self.area.slug}/unregister_participant/response",
                             json.dumps({"response": "failed"}))
            else:
                self.publish(f"{self.area.slug}/unregister_participant/response",
                             json.dumps({"response": "success"}))
                area_object.strategy.shutdown()

        self.areas_to_unregister = []

    def register_new_areas(self):
        if not self.areas_to_register:
            return
        for new_area in self.areas_to_register:
            area_object = self.area.__class__(name=new_area)
            area_object.parent = self.area
            self.area.children.append(area_object)
            area_object.strategy = ExternalStrategy(area_object)
            area_object.activate()

            self.publish(f"{self.area.slug}/register_participant/response",
                         self._subscribe_channel_list(area_object))
        self.areas_to_register = []

    def _subscribe_channel_list(self, new_area):
        return json.dumps(new_area.strategy.get_channel_list())

    def publish(self, channel, data):
        self.redis_db.publish(channel, data)

    def channel_register_callback(self, payload):
        payload_data = json.loads(payload["data"])
        area_name = payload_data["name"]
        self.areas_to_register.append(area_name)

    def channel_unregister_callback(self, payload):
        payload_data = json.loads(payload["data"])
        area_name = payload_data["name"]
        self.areas_to_unregister.append(area_name)

    def sub_to_area_event(self):
        channel = f"{self.area.slug}/register_participant"
        channel_unregister = f"{self.area.slug}/unregister_participant"

        self.pubsub.subscribe(**{channel: self.channel_register_callback,
                                 channel_unregister: self.channel_unregister_callback})
        self.pubsub.run_in_thread(daemon=True)
