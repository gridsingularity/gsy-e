import json
from random import random
from copy import deepcopy
from d3a.events import MarketEvent
from d3a.models.area.redis_dispatcher import RedisEventDispatcherBase
from d3a.models.market.market_structures import trade_from_JSON_string, offer_from_JSON_string

from threading import Event


class RedisMarketEventDispatcher(RedisEventDispatcherBase):
    def __init__(self, area, root_dispatcher, redis):
        super().__init__(area, root_dispatcher, redis)
        self.str_market_events = [event.name.lower() for event in MarketEvent]
        self.active_trade = False
        self.deferred_events = []
        self.events_to_wait = {
            MarketEvent.OFFER: Event(),
            MarketEvent.OFFER_CHANGED: Event(),
            MarketEvent.TRADE: Event(),
            MarketEvent.OFFER_DELETED: Event()
        }

    def event_channel_name(self):
        return f"{self.area.slug}/market_event"

    def event_response_channel_name(self):
        return f"{self.area.slug}/market_event_response"

    def event_listener_redis(self, payload):
        event_type, kwargs = self.parse_market_event_from_event_payload(payload)

        # If this is a trade-related event, it needs to be executed immediately, all other
        # events need to be stored for deferred execution
        if self.active_trade and event_type not in self._trade_related_events:
            self.store_deferred_events_during_active_trade(payload)
        # If there is no active trade but we still have deferred events, we need to handle these.
        elif not self.active_trade and len(self.deferred_events) > 0:
            self.store_deferred_events_during_active_trade(payload)
            self.run_deferred_events()
        # No deferred event, handle directly the event
        else:
            # Consume already deferred events before handling the new one
            from concurrent.futures import ThreadPoolExecutor
            executor = ThreadPoolExecutor(max_workers=1)

            def executor_func():
                self.root_dispatcher.event_listener(event_type=event_type, **kwargs)
                self.publish_response(event_type)

            executor.submit(executor_func)

    def response_callback(self, payload):
        data = json.loads(payload["data"])

        if "response" in data:
            event_type = data["response"]
            event_type_id = data["event_type"]
            if event_type not in self.str_market_events:
                raise Exception("RedisAreaDispatcher: Should never reach this point")
            else:
                self.events_to_wait[MarketEvent(event_type_id)].set()

    def publish_event(self, area_slug, event_type: MarketEvent, **kwargs):
        dispatch_chanel = f"{area_slug}/market_event"

        for key in ["offer", "trade", "new_offer", "existing_offer"]:
            if key in kwargs:
                kwargs[key] = kwargs[key].to_JSON_string()
        send_data = {"event_type": event_type.value, "kwargs": kwargs}
        self.redis.publish(dispatch_chanel, json.dumps(send_data))

    @property
    def _trade_related_events(self):
        return [MarketEvent.OFFER_CHANGED, MarketEvent.TRADE,
                MarketEvent.BID_TRADED, MarketEvent.BID_CHANGED]

    def broadcast_event_redis(self, event_type: MarketEvent, **kwargs):
        for child in sorted(self.area.children, key=lambda _: random()):
            self.publish_event(child.slug, event_type, **kwargs)
            self.events_to_wait[event_type].wait()
            self.events_to_wait[event_type].clear()

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

    def store_deferred_events_during_active_trade(self, json_event):
        self.deferred_events.append(deepcopy(json_event))

    def run_deferred_events(self):
        if not self.active_trade:
            # Using a while loop in order to avoid for loop crashes when mutating the
            # iterable while in for loop
            while len(self.deferred_events) > 0:
                stored_event = self.deferred_events.pop(0)
                event_type, kwargs = self.parse_market_event_from_event_payload(stored_event)
                self.root_dispatcher.event_listener(event_type=event_type, **kwargs)
                self.publish_response(event_type)
