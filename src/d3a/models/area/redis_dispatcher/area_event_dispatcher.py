import json
from random import random
from d3a.events import AreaEvent
from d3a.models.area.redis_dispatcher import RedisEventDispatcherBase


class RedisAreaEventDispatcher(RedisEventDispatcherBase):
    def __init__(self, area, root_dispatcher, redis):
        super().__init__(area, root_dispatcher, redis)
        self.str_area_events = [event.name.lower() for event in AreaEvent]

    def event_channel_name(self):
        return f"{self.area.slug}/area_event"

    def event_response_channel_name(self):
        return f"{self.area.slug}/area_event_response"

    def response_callback(self, payload):
        data = json.loads(payload["data"])
        if "response" in data:
            event_type = data["response"]
            if event_type in self.str_area_events:
                self.redis.resume()
            else:
                raise Exception("RedisAreaDispatcher: Should never reach this point")

    def publish_area_event(self, area_slug, event_type: AreaEvent, **kwargs):
        send_data = {"event_type": event_type.value, "kwargs": kwargs}
        dispatch_chanel = f"{area_slug}/area_event"
        self.redis.publish(dispatch_chanel, json.dumps(send_data))

    def broadcast_event_redis(self, event_type: AreaEvent, **kwargs):
        for child in sorted(self.area.children, key=lambda _: random()):
            self.publish_area_event(child.slug, event_type, **kwargs)
            self.redis.wait()
            self.root_dispatcher.market_event_dispatcher.cleanup_running_threads()
            self.root_dispatcher.market_notify_event_dispatcher._cleanup_all_running_threads()

        for time_slot, agents in self.root_dispatcher._inter_area_agents.items():
            if time_slot not in self.area._markets.markets:
                # exclude past IAAs
                continue

            if not self.area.events.is_connected:
                break
            for area_name in sorted(agents, key=lambda _: random()):
                agents[area_name].event_listener(event_type, **kwargs)
                # self.root_dispatcher.market_event_dispatcher.cleanup_running_threads()
                self.root_dispatcher.market_notify_event_dispatcher._cleanup_all_running_threads()

    def event_listener_redis(self, payload):
        data = json.loads(payload["data"])
        kwargs = data["kwargs"]
        event_type = AreaEvent(data["event_type"])
        response_channel = f"{self.area.parent.slug}/area_event_response"
        response_data = json.dumps({"response": event_type.name.lower()})

        self.root_dispatcher.event_listener(event_type=event_type, **kwargs)
        self.redis.publish(response_channel, response_data)
