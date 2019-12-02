import json
import logging
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from d3a.d3a_core.redis_connections.redis_area_market_communicator import ResettableCommunicator, \
    BlockingCommunicator
from d3a.events import MarketEvent
from d3a.models.market.market_structures import offer_from_JSON_string, bid_from_JSON_string
from d3a.constants import REDIS_PUBLISH_RESPONSE_TIMEOUT, MAX_WORKER_THREADS


class MarketRedisEventPublisher:
    """
    Used from the Markets class, sends notify events from the Markets to the Areas
    """
    def __init__(self, market_id):
        self.market_id = market_id
        self.redis = BlockingCommunicator()
        self.event_response_uuids = []
        self.futures = []

    def event_channel_name(self):
        return f"market/{self.market_id}/notify_event"

    def event_response_channel_name(self):
        return f"market/{self.market_id}/notify_event/response"

    def response_callback(self, payload):
        data = json.loads(payload["data"])

        if "response" in data:
            self.event_response_uuids.append(data["transaction_uuid"])

    def publish_event(self, event_type: MarketEvent, **kwargs):
        for key in ["offer", "trade", "new_offer", "existing_offer",
                    "bid", "new_bid", "existing_bid", "bid_trade"]:
            if key in kwargs:
                kwargs[key] = kwargs[key].to_JSON_string()
        send_data = {"event_type": event_type.value, "kwargs": kwargs,
                     "transaction_uuid": str(uuid4())}

        self.redis.sub_to_channel(self.event_response_channel_name(), self.response_callback)
        self.redis.publish(self.event_channel_name(), json.dumps(send_data))
        self._wait_for_event_response(send_data)

    def _wait_for_event_response(self, send_data):
        def event_response_was_received_callback():
            return send_data["transaction_uuid"] in self.event_response_uuids

        self.redis.poll_until_response_received(event_response_was_received_callback)

        if send_data["transaction_uuid"] not in self.event_response_uuids:
            logging.error(f"Transaction ID not found after {REDIS_PUBLISH_RESPONSE_TIMEOUT} "
                          f"seconds: {send_data} {self.market_id}")
        else:
            self.event_response_uuids.remove(send_data["transaction_uuid"])


class MarketRedisEventSubscriber:
    def __init__(self, market):
        self.market = market
        self.redis_db = ResettableCommunicator()
        self.sub_to_external_requests()
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKER_THREADS)
        self.futures = []

    def sub_to_external_requests(self):
        self.redis_db.sub_to_multiple_channels({
            self._offer_channel: self._offer,
            self._delete_offer_channel: self._delete_offer,
            self._accept_offer_channel: self._accept_offer,
        })

    def _stop_futures(self):
        for future in self.futures:
            try:
                future.result(timeout=5)
            except TimeoutError:
                logging.error(f"future {future} timed out")
        self.futures = []
        # Stopping executor
        self.executor.shutdown(wait=True)

    def stop(self):
        self._stop_futures()
        self.redis_db.terminate_connection()

    def publish(self, channel, data):
        self.redis_db.publish(channel, json.dumps(data))

    @property
    def _offer_channel(self):
        return f"{self.market.id}/OFFER"

    @property
    def _delete_offer_channel(self):
        return f"{self.market.id}/DELETE_OFFER"

    @property
    def _accept_offer_channel(self):
        return f"{self.market.id}/ACCEPT_OFFER"

    @property
    def _offer_response_channel(self):
        return f"{self._offer_channel}/RESPONSE"

    @property
    def _delete_offer_response_channel(self):
        return f"{self._delete_offer_channel}/RESPONSE"

    @property
    def _accept_offer_response_channel(self):
        return f"{self._accept_offer_channel}/RESPONSE"

    @classmethod
    def _parse_payload(cls, payload):
        data_dict = json.loads(payload["data"])
        return cls.sanitize_parameters(data_dict)

    @classmethod
    def sanitize_parameters(cls, data_dict):
        if "offer_or_id" in data_dict and data_dict["offer_or_id"] is not None:
            if isinstance(data_dict["offer_or_id"], str):
                data_dict["offer_or_id"] = offer_from_JSON_string(data_dict["offer_or_id"])
        if "offer" in data_dict and data_dict["offer"] is not None:
            if isinstance(data_dict["offer"], str):
                data_dict["offer"] = offer_from_JSON_string(data_dict["offer"])

        return data_dict

    def _accept_offer(self, payload):
        def thread_cb():
            return self._accept_offer_impl(self._parse_payload(payload))
        self.futures.append(self.executor.submit(thread_cb))

    def _accept_offer_impl(self, arguments):
        transaction_uuid = arguments.pop("transaction_uuid", None)
        try:
            trade = self.market.accept_offer(**arguments)
            self.publish(self._accept_offer_response_channel,
                         {"status": "ready", "trade": trade.to_JSON_string(),
                          "transaction_uuid": transaction_uuid})
        except Exception as e:
            logging.error(f"Error when handling accept_offer on market {self.market.name}: "
                          f"Exception: {str(e)}, Accept Offer Arguments: {arguments}")
            self.publish(self._accept_offer_response_channel,
                         {"status": "error",  "exception": str(type(e)),
                          "error_message": str(e), "transaction_uuid": transaction_uuid})

    def _offer(self, payload):
        def thread_cb():
            return self._offer_impl(self._parse_payload(payload))

        self.futures.append(self.executor.submit(thread_cb))

    def _offer_impl(self, arguments):
        transaction_uuid = arguments.pop("transaction_uuid", None)
        try:
            offer = self.market.offer(**arguments)
            self.publish(self._offer_response_channel,
                         {"status": "ready", "offer": offer.to_JSON_string(),
                          "transaction_uuid": transaction_uuid})
        except Exception as e:
            logging.error(f"Error when handling offer on market {self.market.name}: "
                          f"Exception: {str(e)}, Offer Arguments: {arguments}")
            self.publish(self._offer_response_channel,
                         {"status": "error",  "exception": str(type(e)),
                          "error_message": str(e), "transaction_uuid": transaction_uuid})

    def _delete_offer(self, payload):

        def thread_cb():
            return self._delete_offer_impl(self._parse_payload(payload))
        self.futures.append(self.executor.submit(thread_cb))

    def _delete_offer_impl(self, arguments):
        transaction_uuid = arguments.pop("transaction_uuid", None)
        try:
            self.market.delete_offer(**arguments)

            self.publish(self._delete_offer_response_channel,
                         {"status": "ready", "transaction_uuid": transaction_uuid})
        except Exception as e:
            logging.debug(f"Error when handling delete_offer on market {self.market.name}: "
                          f"Exception: {str(e)}, Delete Offer Arguments: {arguments}")
            self.publish(self._delete_offer_response_channel,
                         {"status": "ready", "exception": str(type(e)),
                          "error_message": str(e), "transaction_uuid": transaction_uuid})


class TwoSidedMarketRedisEventSubscriber(MarketRedisEventSubscriber):
    def __init__(self, market):
        super().__init__(market)

    def sub_to_external_requests(self):
        self.redis_db.sub_to_multiple_channels({
            self._offer_channel: self._offer,
            self._delete_offer_channel: self._delete_offer,
            self._accept_offer_channel: self._accept_offer,
            self._bid_channel: self._bid,
            self._delete_bid_channel: self._delete_bid,
            self._accept_bid_channel: self._accept_bid,
            self._clear_market_channel: self._clear_market,
        })

    @property
    def _bid_channel(self):
        return f"{self.market.id}/BID"

    @property
    def _delete_bid_channel(self):
        return f"{self.market.id}/DELETE_BID"

    @property
    def _accept_bid_channel(self):
        return f"{self.market.id}/ACCEPT_BID"

    @property
    def _clear_market_channel(self):
        return f"{self.market.id}/CLEAR"

    @property
    def _bid_response_channel(self):
        return f"{self._bid_channel}/RESPONSE"

    @property
    def _delete_bid_response_channel(self):
        return f"{self._delete_bid_channel}/RESPONSE"

    @property
    def _accept_bid_response_channel(self):
        return f"{self._accept_bid_channel}/RESPONSE"

    @property
    def _clear_market_response_channel(self):
        return f"{self._clear_market_channel}/RESPONSE"

    @classmethod
    def sanitize_parameters(cls, data_dict):
        data_dict = super().sanitize_parameters(data_dict)
        if "bid_or_id" in data_dict and data_dict["bid_or_id"] is not None:
            if isinstance(data_dict["bid_or_id"], str):
                data_dict["bid_or_id"] = bid_from_JSON_string(data_dict["bid_or_id"])
        if "bid" in data_dict and data_dict["bid"] is not None:
            if isinstance(data_dict["bid"], str):
                data_dict["bid"] = bid_from_JSON_string(data_dict["bid"])

        return data_dict

    def _accept_bid(self, payload):
        def thread_cb():
            return self._accept_bid_impl(self._parse_payload(payload))
        self.futures.append(self.executor.submit(thread_cb))

    def _accept_bid_impl(self, arguments):
        transaction_uuid = arguments.pop("transaction_uuid", None)
        try:
            trade = self.market.accept_bid(**arguments)
            self.publish(self._accept_bid_response_channel,
                         {"status": "ready", "trade": trade.to_JSON_string(),
                          "transaction_uuid": transaction_uuid})
        except Exception as e:
            logging.error(f"Error when handling accept_bid on market {self.market_object.name}: "
                          f"Exception: {str(e)}, Accept Bid Arguments: {arguments}")
            self.publish(self._accept_bid_response_channel,
                         {"status": "error",  "exception": str(type(e)),
                          "error_message": str(e), "transaction_uuid": transaction_uuid})

    def _bid(self, payload):
        def thread_cb():
            return self._bid_impl(self._parse_payload(payload))

        self.futures.append(self.executor.submit(thread_cb))

    def _bid_impl(self, arguments):
        transaction_uuid = arguments.pop("transaction_uuid", None)
        try:
            bid = self.market.bid(**arguments)
            self.publish(self._bid_response_channel,
                         {"status": "ready", "bid": bid.to_JSON_string(),
                          "transaction_uuid": transaction_uuid})
        except Exception as e:
            logging.error(f"Error when handling bid create on market {self.market_object.name}: "
                          f"Exception: {str(e)}, Bid Arguments: {arguments}")
            self.publish(self._bid_response_channel,
                         {"status": "error",  "exception": str(type(e)),
                          "error_message": str(e), "transaction_uuid": transaction_uuid})

    def _delete_bid(self, payload):
        def thread_cb():
            return self._delete_bid_impl(self._parse_payload(payload))
        self.futures.append(self.executor.submit(thread_cb))

    def _delete_bid_impl(self, arguments):
        transaction_uuid = arguments.pop("transaction_uuid", None)
        try:
            self.market.delete_bid(**arguments)

            self.publish(self._delete_bid_response_channel,
                         {"status": "ready", "transaction_uuid": transaction_uuid})
        except Exception as e:
            logging.debug(f"Error when handling bid delete on market {self.market_object.name}: "
                          f"Exception: {str(e)}, Delete Bid Arguments: {arguments}")
            self.publish(self._delete_bid_response_channel,
                         {"status": "ready", "exception": str(type(e)),
                          "error_message": str(e), "transaction_uuid": transaction_uuid})

    def _clear_market(self, payload):
        def thread_cb():
            return self._clear_market_impl(self._parse_payload(payload))
        self.futures.append(self.executor.submit(thread_cb))

    def _clear_market_impl(self, arguments):
        transaction_uuid = arguments.pop("transaction_uuid", None)
        try:
            self.market.match_offers_bids()
            self.publish(self._clear_market_response_channel,
                         {"status": "ready", "transaction_uuid": transaction_uuid})
        except Exception as e:
            logging.error(
                f"Error when handling market clearing event on market {self.market.name}: "
                f"Exception {str(e)}")
            self.publish(self._clear_market_response_channel,
                         {"status": "ready", "exception": str(type(e)),
                          "error_message": str(e), "transaction_uuid": transaction_uuid})
