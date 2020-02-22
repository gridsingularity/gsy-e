from redis import StrictRedis
import json
from d3a.d3a_core.redis_connections.redis_communication import REDIS_URL


class RedisMarketExternalConnection:
    def __init__(self, area):
        self.area = area
        self.redis_db = StrictRedis.from_url(REDIS_URL, retry_on_timeout=True)
        self.pubsub = self.redis_db.pubsub()
        self.sub_to_area_event()

    def publish(self, channel, data):
        self.redis_db.publish(channel, data)

    @property
    def _market_stats_channel(self):
        return f"market_stats/{self.area.slug}"

    def sub_to_area_event(self):
        self.pubsub.subscribe(**{self._market_stats_channel: self.market_stats_callback})
        self.pubsub.run_in_thread(daemon=True)

    def market_stats_callback(self, payload):
        market_stats_response_channel = f"{self._market_stats_channel}/response"
        payload_data = json.loads(payload["data"])
        ret_val = {"status": "ready",
                   "market_stats":
                       self.area.stats.get_market_price_stats(payload_data["market_slots"])}
        self.publish(market_stats_response_channel, json.dumps(ret_val))
