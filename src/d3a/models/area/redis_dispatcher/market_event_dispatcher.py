import json
from random import random
from d3a.models.area.redis_dispatcher.redis_communicator import RedisAreaCommunicator
from d3a.events import MarketEvent
from d3a.models.market.market_structures import trade_from_JSON_string, offer_from_JSON_string


class RedisMarketEventDispatcher:
    def __init__(self, area, root_dispatcher):
        self.area = area
        self.root_dispatcher = root_dispatcher
        self.redis = RedisAreaCommunicator()
        self.subscribe_to_event_responses()
        self.subscribe_to_events()
        self.str_market_events = [event.name.lower() for event in MarketEvent]
        self.active_trade = True
        self.deferred_events = []

    def subscribe_to_event_responses(self):
        channel = f"{self.area.slug}/market_event_response"
        self.redis.sub_to_response(channel, self.response_callback)

    def subscribe_to_events(self):
        channel = f"{self.area.slug}/market_event"
        self.redis.sub_to_area_event(channel, self.event_listener_redis)

    def event_listener_redis(self, payload):
        event_type, kwargs = self.parse_market_event_from_event_payload(payload)

        # If this is a trade-related event, it needs to be executed immediately, all other
        # events need to be stored for deferred execution
        if self.active_trade and event_type in [MarketEvent.OFFER, MarketEvent.OFFER_DELETED,
                                                MarketEvent.BID_DELETED]:
            self.store_deferred_events_during_active_trade(payload)
        # If there is no active trade but we still have deferred events, we need to handle these.
        elif not self.active_trade and len(self.deferred_events) > 0:
            self.store_deferred_events_during_active_trade(payload)
            self.run_deferred_events()
        # No deferred event, handle directly the event
        else:
            # Consume already deferred events before handling the new one
            self.root_dispatcher.event_listener(event_type=event_type, **kwargs)
            self.publish_response(event_type)

    def response_callback(self, payload):
        data = json.loads(payload["data"])

        if "response" in data:
            event_type = data["response"]
            if event_type not in self.str_market_events:
                raise Exception("RedisAreaDispatcher: Should never reach this point")
            else:
                if self.active_trade:
                    self.redis.resume()

    def publish_event(self, area_slug, event_type: MarketEvent, **kwargs):
        dispatch_chanel = f"{area_slug}/market_event"

        for key in ["offer", "trade", "new_offer", "existing_offer"]:
            if key in kwargs:
                kwargs[key] = kwargs[key].to_JSON_string()
        send_data = {"event_type": event_type.value, "kwargs": kwargs}
        self.redis.publish(dispatch_chanel, json.dumps(send_data))

    def broadcast_market_event_redis(self, event_type: MarketEvent, **kwargs):
        # Decides whether this event is starting an active trade. This will defer
        # all events other than trade-related events.
        if event_type == MarketEvent.OFFER_CHANGED:
            self.active_trade = True

        for child in sorted(self.area.children, key=lambda _: random()):
            self.publish_event(child.slug, event_type, **kwargs)
            if self.active_trade and event_type in [MarketEvent.OFFER_CHANGED, MarketEvent.TRADE]:
                self.redis.wait()

        for time_slot, agents in self.root_dispatcher._inter_area_agents.items():
            if time_slot not in self.area._markets.markets:
                # exclude past IAAs
                continue

            if not self.area.events.is_connected:
                break
            for area_name in sorted(agents, key=lambda _: random()):
                agents[area_name].event_listener(event_type, **kwargs)

        # Decides whether the execution of this event has completed the trade
        if event_type == MarketEvent.TRADE and self.active_trade is True:
            self.active_trade = False

    def publish_response(self, event_type):
        response_channel = f"{self.area.parent.slug}/market_event_response"
        response_data = json.dumps({"response": event_type.name.lower()})
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
        from copy import deepcopy
        self.deferred_events.append(deepcopy(json_event))

    def run_deferred_events(self):
        if not self.active_trade:
            # Using a while loop in order to avoid for loop crashes when mutating the
            # iterable while in for loop
            while len(self.deferred_events) > 0:
                stored_event = self.deferred_events.pop(0)
                if type(stored_event) == str:
                    assert False
                event_type, kwargs = self.parse_market_event_from_event_payload(stored_event)
                self.root_dispatcher.event_listener(event_type=event_type, **kwargs)
                self.publish_response(event_type)
