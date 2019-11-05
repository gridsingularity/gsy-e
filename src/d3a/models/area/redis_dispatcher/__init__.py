from abc import ABC, abstractmethod


class RedisEventDispatcherBase(ABC):
    def __init__(self, area, root_dispatcher, redis):
        self.area = area
        self.root_dispatcher = root_dispatcher
        self.redis = redis
        self.subscribe_to_event_responses()
        self.subscribe_to_events()

    @abstractmethod
    def event_channel_name(self):
        pass

    @abstractmethod
    def event_response_channel_name(self):
        pass

    def subscribe_to_event_responses(self):
        self.redis.sub_to_response(self.event_response_channel_name(), self.response_callback)

    def subscribe_to_events(self):
        self.redis.sub_to_area_event(self.event_channel_name(), self.event_listener_redis)

    @abstractmethod
    def response_callback(self, payload):
        pass

    @abstractmethod
    def event_listener_redis(self, payload):
        pass

    @abstractmethod
    def broadcast_event_redis(self, event_type, **kwargs):
        pass
