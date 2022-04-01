import json
import logging
from concurrent.futures import ThreadPoolExecutor
from gsy_e.constants import MAX_WORKER_THREADS
from gsy_e.models.market.market_structures import parse_event_and_parameters_from_json_string
from gsy_e.gsy_e_core.redis_connections.area_market_communicator import ResettableCommunicator


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
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKER_THREADS)

    def publish_notify_event_response(self, market_id, event_type, transaction_uuid):
        response_channel = f"market/{market_id}/notify_event/response"
        response_data = json.dumps({"response": event_type.name.lower(),
                                    "event_type_id": event_type.value,
                                    "transaction_uuid": transaction_uuid})
        self.redis.publish(response_channel, response_data)

    def wait_for_futures(self):
        for future in self.futures:
            try:
                future.result(timeout=5)
            except Exception as e:
                logging.error(f"future {future} timed out during cleanup. Exception: {str(e)}")
        self.futures = []

    def cycle_market_channels(self):
        self.wait_for_futures()
        self.redis.terminate_connection()
        self.redis = ResettableCommunicator()
        self.subscribe_to_events()

    def subscribe_to_events(self):
        market = self.area.spot_market
        channel_name = f"market/{market.id}/notify_event"

        def generate_notify_callback(payload):
            event_type, kwargs = self.parse_market_event_from_event_payload(payload)
            data = json.loads(payload["data"])
            kwargs["market_id"] = market.id

            def executor_func():
                transaction_uuid = data.pop("transaction_uuid", None)
                assert transaction_uuid is not None
                self.root_dispatcher.broadcast_notification(event_type, **kwargs)
                self.publish_notify_event_response(market.id, event_type, transaction_uuid)

            self.futures.append(self.executor.submit(executor_func))

        self.redis.sub_to_multiple_channels({channel_name: generate_notify_callback})

    def parse_market_event_from_event_payload(self, payload):
        return parse_event_and_parameters_from_json_string(payload)
