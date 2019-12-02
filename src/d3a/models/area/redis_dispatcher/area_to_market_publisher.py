from uuid import uuid4
import json
from d3a.d3a_core.exceptions import D3ARedisException
from d3a_interface.constants_limits import ConstSettings
from d3a.constants import REDIS_PUBLISH_RESPONSE_TIMEOUT
from d3a.d3a_core.redis_connections.redis_area_market_communicator import BlockingCommunicator


class AreaToMarketEventPublisher:
    def __init__(self, area):
        self.area = area
        self.redis = BlockingCommunicator()
        self.event_response_uuids = []

    def response_callback(self, payload):
        response = json.loads(payload["data"])
        if response["status"] != "ready":
            raise D3ARedisException(
                f"{self.area.name} received an incorrect response from Redis: {response}"
            )
        if "transaction_uuid" not in response:
            raise D3ARedisException(
                f"{self.area.name} received market response without transaction id: {response}"
            )
        self.event_response_uuids.append(response["transaction_uuid"])

    def publish_markets_clearing(self):
        if ConstSettings.IAASettings.MARKET_TYPE == 1:
            return
        for market in self.area._markets.markets.values():
            response_channel = f"{market.id}/CLEAR/RESPONSE"
            market_channel = f"{market.id}/CLEAR"

            data = {"transaction_uuid": str(uuid4())}
            self.redis.sub_to_channel(response_channel, self.response_callback)
            self.redis.publish(market_channel, json.dumps(data))

            def event_response_was_received_callback():
                return data["transaction_uuid"] in self.event_response_uuids

            self.redis.poll_until_response_received(event_response_was_received_callback)

            if data["transaction_uuid"] not in self.event_response_uuids:
                self.area.log.error(
                    f"Transaction ID not found after {REDIS_PUBLISH_RESPONSE_TIMEOUT} "
                    f"seconds: Clearing event on {self.area.name}, {market.id}")
            else:
                self.event_response_uuids.remove(data["transaction_uuid"])
