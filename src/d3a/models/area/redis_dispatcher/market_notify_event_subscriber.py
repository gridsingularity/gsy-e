import json
import logging
from d3a.models.market.market_structures import offer_from_JSON_string, trade_from_JSON_string
from d3a.events import MarketEvent
from d3a.models.area.redis_dispatcher.redis_communicator import ResettableCommunicator
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from redis import StrictRedis
from d3a.d3a_core.redis_communication import REDIS_URL


class MarketNotifyEventPublisher:
    """
    Used from the Markets class, sends notify events from the Markets to the Areas
    """
    def __init__(self, market_id):
        self.market_id = market_id
        self.redis = StrictRedis.from_url(REDIS_URL)
        self.pubsub = self.redis.pubsub()
        self.active_event = False
        self.event_response_uuids = []
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.futures = []
        self.lock = Lock()

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
        data = json.loads(payload["data"])

        if "response" in data:
            self.event_response_uuids.append(data["transaction_uuid"])

    def publish_event(self, event_type: MarketEvent, **kwargs):
        for key in ["offer", "trade", "new_offer", "existing_offer"]:
            if key in kwargs:
                kwargs[key] = kwargs[key].to_JSON_string()
        send_data = {"event_type": event_type.value, "kwargs": kwargs}
        self.pubsub.subscribe(**{self.event_response_channel_name(): self.response_callback})
        from uuid import uuid4
        send_data["transaction_uuid"] = str(uuid4())
        self.redis.publish(self.event_channel_name(), json.dumps(send_data))
        retries = 0
        # TODO: Refactor the retries mechanism
        while send_data["transaction_uuid"] not in self.event_response_uuids and retries < 50:
            retries += 1
            with self.lock:
                self.pubsub.get_message(timeout=0.01)

        if send_data["transaction_uuid"] not in self.event_response_uuids:
            logging.error(f"Transaction ID not found after lots of retries: "
                          f"{send_data} {self.market_id}")
        else:
            self.event_response_uuids.remove(send_data["transaction_uuid"])


class MarketNotifyEventSubscriber:
    """
    Used from the area class, subscribes to the market events and triggers the broadcast_events
    method
    """
    def __init__(self, area, root_dispatcher):
        self.area = area
        self.root_dispatcher = root_dispatcher
        self.redis = ResettableCommunicator()
        self.futures = []
        self.active_trade = False

        self.executor = ThreadPoolExecutor(max_workers=10)

    def publish_notify_event_response(self, market_id, event_type, transaction_uuid):
        response_channel = f"market/{market_id}/notify_event/response"
        response_data = json.dumps({"response": event_type.name.lower(),
                                    "event_type_id": event_type.value,
                                    "transaction_uuid": transaction_uuid})
        self.redis.publish(response_channel, response_data)

    def _cleanup_all_running_threads(self):
        for future in self.futures:
            try:
                future.result(timeout=5)
            except Exception as e:
                logging.error(f"future {future} timed out during cleanup. Exception: {str(e)}")
        self.futures = []

    def cycle_market_channels(self):
        self._cleanup_all_running_threads()
        try:
            self.redis.stop_all_threads()
        except Exception as e:
            logging.debug(f"Error when stopping all threads when recycling markets: {str(e)}")
        self.redis = ResettableCommunicator()
        self.subscribe_to_events()

    def subscribe_to_events(self):
        channels_callbacks_dict = {}
        for market in self.area.all_markets:
            channel_name = f"market/{market.id}/notify_event"

            def generate_notify_callback(payload):
                event_type, kwargs = self.parse_market_event_from_event_payload(payload)
                data = json.loads(payload["data"])
                kwargs["market_id"] = market.id

                def executor_func():
                    transaction_uuid = data.pop("transaction_uuid", None)
                    assert transaction_uuid is not None
                    self.root_dispatcher.broadcast_callback(event_type, **kwargs)
                    self.publish_notify_event_response(market.id, event_type, transaction_uuid)

                self.futures.append(self.executor.submit(executor_func))

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
