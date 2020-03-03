from redis import StrictRedis
import json
import d3a
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
    def channel_prefix(self):
        if d3a.constants.EXTERNAL_CONNECTION_WEB:
            return f"external/{d3a.constants.COLLABORATION_ID}/{self.area.uuid}"
        else:
            return f"{self.area.slug}"

    @property
    def _market_stats_channel(self):
        return f"{self.channel_prefix}/market_stats"

    @property
    def _grid_fees_channel(self):
        return f"{self.channel_prefix}/grid_fees"

    def sub_to_area_event(self):
        self.pubsub.subscribe(**{
            f"{self.channel_prefix}/market_stats": self.market_stats_callback,
            f"{self.channel_prefix}/grid_fees": self.grid_fees_callback
        })
        self.pubsub.run_in_thread(daemon=True)

    def market_stats_callback(self, payload):
        market_stats_response_channel = f"{self.channel_prefix}/response/market_stats"
        payload_data = json.loads(payload["data"])
        ret_val = {"status": "ready",
                   "command": "market_stats",
                   "market_stats":
                       self.area.stats.get_market_stats(payload_data["market_slots"])}
        self.publish(market_stats_response_channel, json.dumps(ret_val))

    def grid_fees_callback(self, payload):
        market_stats_response_channel = f"{self.channel_prefix}/response/grid_fees"
        payload_data = json.loads(payload["data"])
        self.area.transfer_fee_const = payload_data["fee"]
        self.publish(market_stats_response_channel, json.dumps({
            "status": "ready", "command": "grid_fees",
            "fee": str(self.area.transfer_fee_const)})
         )
