from redis import StrictRedis
import json
from d3a.d3a_core.redis_connections.redis_communication import REDIS_URL
from d3a.models.strategy.external_strategy import ExternalStrategy


class RedisAreaExternalConnection:
    def __init__(self, area):
        self.area = area
        self.redis_db = StrictRedis.from_url(REDIS_URL)
        self.pubsub = self.redis_db.pubsub()
        self.sub_to_area_event()
        self.areas_to_register = []

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
                         self._subscribe_channel_list(new_area))
        self.areas_to_register = []

    def _subscribe_channel_list(self, new_area):
        return json.dumps({
            "available_publish_channels": [
                f"{self.area.slug}/{new_area}/offer",
                f"{self.area.slug}/{new_area}/offer_delete",
                f"{self.area.slug}/{new_area}/offer_accept",
            ],
            "available_subscribe_channels": [
                f"{self.area.slug}/{new_area}/offers",
                f"{self.area.slug}/{new_area}/offer/response",
                f"{self.area.slug}/{new_area}/offer_delete/response",
                f"{self.area.slug}/{new_area}/offer_accept/response"
            ]
        })

    def publish(self, channel, data):
        self.redis_db.publish(channel, data)

    def sub_to_area_event(self):
        channel = f"{self.area.slug}/register_participant"

        def channel_callback(payload):
            payload_data = json.loads(payload["data"])
            area_name = payload_data["name"]
            self.areas_to_register.append(area_name)

        self.pubsub.subscribe(**{channel: channel_callback})
        self.pubsub.run_in_thread(daemon=True)
