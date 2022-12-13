import json
import logging
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from gsy_framework.data_classes import BaseBidOffer, Trade, Bid, Offer
from gsy_framework.utils import key_in_dict_and_not_none

from gsy_e.constants import REDIS_PUBLISH_RESPONSE_TIMEOUT, MAX_WORKER_THREADS
from gsy_e.gsy_e_core.redis_connections.area_market import (
    ResettableCommunicator, BlockingCommunicator)
from gsy_e.events import MarketEvent


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
        """Channel name for notifying events."""
        return f"market/{self.market_id}/notify_event"

    def event_response_channel_name(self):
        """Channel name for response of event notification messages."""
        return f"market/{self.market_id}/notify_event/response"

    def response_callback(self, payload):
        """Callback method that gets triggered on response"""
        data = json.loads(payload["data"])

        if "response" in data:
            self.event_response_uuids.append(data["transaction_uuid"])

    def publish_event(self, event_type: MarketEvent, **kwargs):
        """Publish event and wait for the event response."""
        for key in ["offer", "trade", "new_offer", "existing_offer",
                    "bid", "new_bid", "existing_bid", "bid_trade"]:
            if key in kwargs:
                kwargs[key] = kwargs[key].to_json_string()
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
            logging.error("Transaction ID not found after %s seconds: %s %s",
                          REDIS_PUBLISH_RESPONSE_TIMEOUT, send_data, self.market_id)
        else:
            self.event_response_uuids.remove(send_data["transaction_uuid"])


class MarketRedisEventSubscriber:
    """Redis subscriber to the market events."""
    # pylint: disable=broad-except
    def __init__(self, market):
        self.market_object = market
        self.redis_db = ResettableCommunicator()
        self.sub_to_external_requests()
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKER_THREADS)
        self.futures = []

    @property
    def market(self):
        """Market whose events the subscriber listens to."""
        return self.market_object

    def sub_to_external_requests(self):
        """Subscribe to external requests / commands."""
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
                logging.error("future %s timed out", future)
        self.futures = []
        # Stopping executor
        self.executor.shutdown(wait=True)

    def stop(self):
        """Stop the subscriber."""
        self._stop_futures()
        self.redis_db.terminate_connection()

    def _publish(self, channel, data):
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

    @staticmethod
    def _parse_payload(payload):
        data_dict = json.loads(payload["data"])
        retval = MarketRedisEventSubscriber._parse_order_objects(data_dict)
        return retval

    @classmethod
    def _parse_order_objects(cls, data_dict):
        if (key_in_dict_and_not_none(data_dict, "offer_or_id")
                and isinstance(data_dict["offer_or_id"], str)):
            data_dict["offer_or_id"] = BaseBidOffer.from_json(data_dict["offer_or_id"])
        if key_in_dict_and_not_none(data_dict, "offer") and isinstance(data_dict["offer"], str):
            data_dict["offer"] = Offer.from_json(data_dict["offer"])
        if key_in_dict_and_not_none(data_dict, "bid") and isinstance(data_dict["bid"], str):
            data_dict["bid"] = Bid.from_json(data_dict["bid"])
        if key_in_dict_and_not_none(data_dict, "trade") and isinstance(data_dict["trade"], str):
            data_dict["trade"] = Trade.from_json(data_dict["trade"])

        return data_dict

    def _accept_offer(self, payload):
        def thread_cb():
            return self._accept_offer_impl(self._parse_payload(payload))
        self.futures.append(self.executor.submit(thread_cb))

    def _accept_offer_impl(self, arguments):
        transaction_uuid = arguments.pop("transaction_uuid", None)
        try:
            trade = self.market.accept_offer(**arguments)
            self._publish(self._accept_offer_response_channel,
                          {"status": "ready", "trade": trade.to_json_string(),
                           "transaction_uuid": transaction_uuid})
        except Exception as e:
            logging.error("Error when handling accept_offer on market %s: Exception: %s, "
                          "Accept Offer Arguments: %s", self.market.name, str(e), arguments)
            self._publish(self._accept_offer_response_channel,
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
            self._publish(self._offer_response_channel,
                          {"status": "ready", "offer": offer.to_json_string(),
                           "transaction_uuid": transaction_uuid})
        except Exception as e:
            logging.error("Error when handling offer on market %s: Exception: %s, "
                          "Offer Arguments: %s", self.market.name, str(e), arguments)
            self._publish(self._offer_response_channel,
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

            self._publish(self._delete_offer_response_channel,
                          {"status": "ready", "transaction_uuid": transaction_uuid})
        except Exception as e:
            logging.debug("Error when handling delete_offer on market %s: Exception: %s, "
                          "Delete Offer Arguments: %s", self.market.name, str(e), arguments)
            self._publish(self._delete_offer_response_channel,
                          {"status": "ready", "exception": str(type(e)),
                           "error_message": str(e), "transaction_uuid": transaction_uuid})


class TwoSidedMarketRedisEventSubscriber(MarketRedisEventSubscriber):
    """Redis subscriber to the two sided market events."""
    # pylint: disable=broad-except
    def sub_to_external_requests(self):
        self.redis_db.sub_to_multiple_channels({
            self._offer_channel: self._offer,
            self._delete_offer_channel: self._delete_offer,
            self._accept_offer_channel: self._accept_offer,
            self._bid_channel: self._bid,
            self._delete_bid_channel: self._delete_bid,
            self._accept_bid_channel: self._accept_bid,
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
    def _bid_response_channel(self):
        return f"{self._bid_channel}/RESPONSE"

    @property
    def _delete_bid_response_channel(self):
        return f"{self._delete_bid_channel}/RESPONSE"

    @property
    def _accept_bid_response_channel(self):
        return f"{self._accept_bid_channel}/RESPONSE"

    def _accept_bid(self, payload):
        def thread_cb():
            return self._accept_bid_impl(self._parse_payload(payload))
        self.futures.append(self.executor.submit(thread_cb))

    def _accept_bid_impl(self, arguments):
        transaction_uuid = arguments.pop("transaction_uuid", None)
        try:
            trade = self.market.accept_bid(**arguments)
            self._publish(self._accept_bid_response_channel,
                          {"status": "ready", "trade": trade.to_json_string(),
                           "transaction_uuid": transaction_uuid})
        except Exception as e:
            logging.error("Error when handling accept_bid on market %s: Exception: %s, "
                          "Accept Bid Arguments: %s", self.market.name, str(e), arguments)
            self._publish(self._accept_bid_response_channel,
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
            self._publish(self._bid_response_channel,
                          {"status": "ready", "bid": bid.to_json_string(),
                           "transaction_uuid": transaction_uuid})
        except Exception as e:
            logging.error("Error when handling bid create on market %s: Exception: %s, "
                          "Bid Arguments: %s", self.market.name, str(e), arguments)
            self._publish(self._bid_response_channel,
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

            self._publish(self._delete_bid_response_channel,
                          {"status": "ready", "transaction_uuid": transaction_uuid})
        except Exception as e:
            logging.debug("Error when handling bid delete on market %s: Exception: %s, "
                          "Delete Bid Arguments: %s", self.market.name, str(e), arguments)
            self._publish(self._delete_bid_response_channel,
                          {"status": "ready", "exception": str(type(e)),
                           "error_message": str(e), "transaction_uuid": transaction_uuid})
