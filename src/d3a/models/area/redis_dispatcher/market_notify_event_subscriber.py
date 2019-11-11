import json
from d3a.models.market.market_structures import offer_from_JSON_string, trade_from_JSON_string
from d3a.events import MarketEvent


class MarketNotifyEventPublisher:
    """
    Used from the Markets class, sends notify events from the Markets to the Areas
    """
    def __init__(self, market_id, redis):
        self.market_id = market_id
        self.redis = redis
        self.active_event = False
        self.subscribe_to_event_responses()

    def stop(self):
        try:
            print(f"STOPPING ALL THREADS FROM {self.market_id}")
            self.redis.stop_all_threads()
            print(f"STOPPED ALL THREADS")
        except Exception as e:
            print(f"STOP NOTIFY MARKET PUBLISHER {e}")

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
    def __init__(self, area, root_dispatcher, redis):
        self.area = area
        self.root_dispatcher = root_dispatcher
        self.redis = redis
        self.subscribe_to_events()
        self.futures = []
        self.executors = []

    def publish_notify_event_response(self, market_id, event_type):
        response_channel = f"market/{market_id}/notify_event/response"
        response_data = json.dumps({"response": event_type.name.lower()})
        self.redis.publish(response_channel, response_data)

    def cycle_market_channels(self):
        self.redis.reset_connection()
        for future in self.futures:
            while not future.done():
                from time import sleep
                print(f"SLEEPING ON FUTURE {future} AREA {self.area.name}")
                sleep(1)
        for executor in self.executors:
            executor.shutdown(wait=False)
        self.subscribe_to_events()

    def subscribe_to_events(self):
        channels_callbacks_dict = {}
        for market in self.area.all_markets:
            channel_name = f"market/{market.id}/notify_event"

            def generate_notify_callback(payload):
                event_type, kwargs = self.parse_market_event_from_event_payload(payload)
                kwargs["market_id"] = market.id

                if event_type in [MarketEvent.OFFER, MarketEvent.OFFER_CHANGED,
                                  MarketEvent.TRADE, MarketEvent.OFFER_DELETED]:
                    from concurrent.futures import ThreadPoolExecutor
                    executor = ThreadPoolExecutor(max_workers=1)

                    def executor_func():
                        self.root_dispatcher.broadcast_callback(event_type, **kwargs)
                        self.publish_notify_event_response(market.id, event_type)

                    self.futures.append(executor.submit(executor_func))
                    self.executors.append(executor)
                else:
                    self.root_dispatcher.broadcast_callback(event_type, **kwargs)
                    self.publish_notify_event_response(market.id, event_type)

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
