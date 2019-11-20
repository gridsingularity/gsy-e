import json
import logging
from random import random
from d3a.events import MarketEvent
from d3a.models.area.redis_dispatcher import RedisEventDispatcherBase
from d3a.models.market.market_structures import trade_from_JSON_string, offer_from_JSON_string

from threading import Event


class RedisMarketEventDispatcher(RedisEventDispatcherBase):
    def __init__(self, area, root_dispatcher, redis):
        super().__init__(area, root_dispatcher, redis)
        self.str_market_events = [event.name.lower() for event in MarketEvent]
        self.market_event = Event()
        self.futures = []
        from concurrent.futures import ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.thread_events = {
            MarketEvent.TRADE.value: Event(),
            MarketEvent.OFFER.value: Event(),
            MarketEvent.OFFER_DELETED.value: Event(),
            MarketEvent.OFFER_CHANGED.value: Event(),
        }

    def cleanup_running_threads(self):
        from concurrent.futures import TimeoutError
        for future in self.futures:
            try:
                future.result(timeout=5)
            except TimeoutError:
                logging.error(f"market event future {future} timed out during cleanup.")
        self.futures = []

    def event_channel_name(self):
        return f"{self.area.slug}/market_event"

    def event_response_channel_name(self):
        return f"{self.area.slug}/market_event_response"

    def event_listener_redis(self, payload):
        event_type, kwargs = self.parse_market_event_from_event_payload(payload)

        def executor_func():
            self.root_dispatcher.event_listener(event_type=event_type, **kwargs)
            self.publish_response(event_type)

        self.futures.append(self.executor.submit(executor_func))

    def response_callback(self, payload):
        data = json.loads(payload["data"])

        if "response" in data:
            event_type = data["response"]
            event_type_id = data["event_type"]
            if event_type not in self.str_market_events:
                raise Exception("RedisAreaDispatcher: Should never reach this point")
            else:
                self.thread_events[event_type_id].set()

    def publish_event(self, area_slug, event_type: MarketEvent, **kwargs):
        dispatch_chanel = f"{area_slug}/market_event"

        for key in ["offer", "trade", "new_offer", "existing_offer"]:
            if key in kwargs:
                kwargs[key] = kwargs[key].to_JSON_string()
        send_data = {"event_type": event_type.value, "kwargs": kwargs}
        self.redis.publish(dispatch_chanel, json.dumps(send_data))

    def broadcast_event_redis(self, event_type: MarketEvent, **kwargs):
        for child in sorted(self.area.children, key=lambda _: random()):
            if len(child.children) > 0:
                self.publish_event(child.slug, event_type, **kwargs)
                self.thread_events[event_type.value].wait()
                self.thread_events[event_type.value].clear()
            else:
                child.dispatcher.event_listener(event_type, **kwargs)

        for time_slot, agents in self.root_dispatcher._inter_area_agents.items():
            if time_slot not in self.area._markets.markets:
                # exclude past IAAs
                continue

            if not self.area.events.is_connected:
                break
            for area_name in sorted(agents, key=lambda _: random()):
                agents[area_name].event_listener(event_type, **kwargs)

    def publish_response(self, event_type):
        response_channel = f"{self.area.parent.slug}/market_event_response"
        response_data = json.dumps({"response": event_type.name.lower(),
                                    "event_type": event_type.value})
        self.redis.publish(response_channel, response_data)

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
