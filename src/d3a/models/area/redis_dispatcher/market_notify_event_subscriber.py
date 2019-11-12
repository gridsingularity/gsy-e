import json
import logging
from d3a.models.market.market_structures import offer_from_JSON_string, trade_from_JSON_string
from d3a.events import MarketEvent
from d3a.models.area.redis_dispatcher.redis_communicator import ResettableCommunicator
from time import sleep


class MarketNotifyEventPublisher:
    """
    Used from the Markets class, sends notify events from the Markets to the Areas
    """
    def __init__(self, market_id):
        self.market_id = market_id
        self.redis = ResettableCommunicator()
        self.active_event = False
        self.subscribe_to_event_responses()

    def stop(self):
        try:
            self.redis.stop_all_threads()
        except Exception as e:
            logging.debug(f"Error when stopping all threads: {e}")

    def event_channel_name(self):
        return f"market/{self.market_id}/notify_event"

    def event_response_channel_name(self):
        return f"market/{self.market_id}/notify_event/response"

    def response_callback(self, payload):
        self.redis.resume()

    def subscribe_to_event_responses(self):
        self.redis.sub_to_response(self.event_response_channel_name(), self.response_callback)

    def publish_event(self, event_type: MarketEvent, **kwargs):
        for key in ["offer", "trade", "new_offer", "existing_offer"]:
            if key in kwargs:
                kwargs[key] = kwargs[key].to_JSON_string()
        send_data = {"event_type": event_type.value, "kwargs": kwargs}
        self.redis.publish(self.event_channel_name(), json.dumps(send_data))
        self.redis.wait()


class MarketNotifyEventSubscriber:
    """
    Used from the area class, subscribes to the market events and triggers the broadcast_events
    method
    """
    def __init__(self, area, root_dispatcher):
        self.area = area
        self.root_dispatcher = root_dispatcher
        self.redis = ResettableCommunicator()
        self.subscribe_to_events()
        self.futures = []
        self.executors = []
        self.active_trade = False

    def publish_notify_event_response(self, market_id, event_type):
        response_channel = f"market/{market_id}/notify_event/response"
        response_data = json.dumps({"response": event_type.name.lower()})
        self.redis.publish(response_channel, response_data)

    def _cleanup_all_running_threads(self):
        for future in self.futures:
            while not future.done():
                # Wait for future to finish
                sleep(0.1)
        for executor in self.executors:
            executor.shutdown(wait=False)
        self.futures = []
        self.executors = []

    def cycle_market_channels(self):
        self._cleanup_all_running_threads()
        try:
            self.redis.stop_all_threads()
        except Exception as e:
            logging.debug(f"Error when stopping all threads when recycling markets: {e}")
        self.redis = ResettableCommunicator()
        self.subscribe_to_events()

    def subscribe_to_events(self):
        channels_callbacks_dict = {}
        for market in self.area.all_markets:
            channel_name = f"market/{market.id}/notify_event"

            def generate_notify_callback(payload):
                event_type, kwargs = self.parse_market_event_from_event_payload(payload)
                kwargs["market_id"] = market.id

                from concurrent.futures import ThreadPoolExecutor
                executor = ThreadPoolExecutor(max_workers=1)

                def executor_func():
                    while self.active_trade is True and event_type == MarketEvent.OFFER:
                        # Wait if there is an active trade and a new offer arrives.
                        # This helps to avoid having 2 concurrent trades in one area.
                        sleep(0.5)
                    self.active_trade = event_type in [MarketEvent.OFFER_CHANGED,
                                                       MarketEvent.TRADE]
                    self.root_dispatcher.broadcast_callback(event_type, **kwargs)
                    self.publish_notify_event_response(market.id, event_type)
                    if self.active_trade is not MarketEvent.OFFER_DELETED:
                        self.active_trade = False

                self.futures.append(executor.submit(executor_func))
                self.executors.append(executor)

            channels_callbacks_dict[channel_name] = generate_notify_callback
        self.redis.sub_to_multiple_channels(channels_callbacks_dict)

    def parse_market_event_from_event_payload(self, payload):
        data = json.loads(payload["data"])
        kwargs = data["kwargs"]
        for key in ["offer", "existing_offer", "new_offer"]:
            if key in kwargs:
                kwargs[key] = offer_from_JSON_string(kwargs[key])
        if "trade" in kwargs:
            kwargs["trade"] = trade_from_JSON_string(kwargs["trade"])
        event_type = MarketEvent(data["event_type"])
        return event_type, kwargs
