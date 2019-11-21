from abc import ABC, abstractmethod


class RedisEventDispatcherBase(ABC):
    """
    Interface for adding dispatchers for different event types. The main responsibility
    for the classes that implement this interface is to implement the logic about what
    takes place when an event is received via Redis, and how to propagate this event.
    """
    def __init__(self, area, root_dispatcher, redis):
        self.area = area
        self.root_dispatcher = root_dispatcher
        self.redis = redis
        self.subscribe_to_event_responses()
        self.subscribe_to_events()

    @abstractmethod
    def event_channel_name(self):
        """
        Channel name that the area subscribes to. It is used to listen to events
        that originate from the parent area.
        :return: String that contains the channel name for the area
        """
        pass

    @abstractmethod
    def event_response_channel_name(self):
        """
        Channel name that the area subscribes to get informed about responses for the
        broadcasted events to its children
        :return: String that contains the response channel name
        """
        pass

    def subscribe_to_events(self):
        """
        Subscribes to the channel that receives events from the parent area.
        :return: None
        """
        self.redis.sub_to_area_event(self.event_channel_name(), self.event_listener_redis)

    def subscribe_to_event_responses(self):
        """
        Subscribes to the channel that receives responses from the events broadcasted to the
        area children
        :return: None
        """
        self.redis.sub_to_response(self.event_response_channel_name(), self.response_callback)

    @abstractmethod
    def response_callback(self, payload):
        """
        Callback that gets triggered when a message is received on event_response_channel_name
        channel. Will handle responses from broadcasted events to children.
        :param payload: JSON String with the response payload
        :return: None
        """
        pass

    @abstractmethod
    def event_listener_redis(self, payload):
        """
        Responsible for consuming the events that the area receives from its parent on the
        event_channel_name channel. Triggers the necessary area/strategy actions depending to
        the event type.
        :param payload: JSON String with the parent event payload
        :return: None
        """
        pass

    @abstractmethod
    def broadcast_event_redis(self, event_type, **kwargs):
        """
        Responsible for broadcasting an event to the child areas and to the IAAs of the area.
        :param event_type: Type of the event that is broadcasted
        :param kwargs: Arguments of the event
        :return: None
        """
        pass
