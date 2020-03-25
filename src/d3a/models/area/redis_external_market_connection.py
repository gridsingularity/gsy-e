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

    def publish_json(self, channel, data):
        self.redis_db.publish(channel, json.dumps(data))

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
            f"{self.channel_prefix}/dso_market_stats": self.dso_market_stats_callback,
            f"{self.channel_prefix}/grid_fees": self.set_grid_fees_callback
        })
        self.pubsub.run_in_thread(daemon=True)

    def market_stats_callback(self, payload):
        market_stats_response_channel = f"{self.channel_prefix}/response/market_stats"
        payload_data = json.loads(payload["data"])
        ret_val = {"status": "ready",
                   "command": "market_stats",
                   "market_fee_const":
                       self.area.stats.get_market_stats(payload_data["market_slots"]),
                   "transaction_id": payload_data.get("transaction_id", None)}
        self.publish_json(market_stats_response_channel, ret_val)

    def set_grid_fees_callback(self, payload):
        market_stats_response_channel = f"{self.channel_prefix}/response/grid_fees"
        payload_data = json.loads(payload["data"])
        self.area.transfer_fee_const = payload_data["fee"]
        self.publish_json(market_stats_response_channel, {
            "status": "ready", "command": "grid_fees",
            "market_fee_const": str(self.area.transfer_fee_const),
            "transaction_id": payload_data.get("transaction_id", None)}
         )

    def dso_market_stats_callback(self, payload):
        market_stats_response_channel = f"{self.channel_prefix}/response/dso_market_stats"
        payload_data = json.loads(payload["data"])
        ret_val = {"status": "ready",
                   "command": "dso_market_stats",
                   "market_stats":
                       self.area.stats.get_market_stats(payload_data["market_slots"]),
                   "market_fee_const": str(self.area.transfer_fee_const),
                   "transaction_id": payload_data.get("transaction_id", None)}
        self.publish_json(market_stats_response_channel, ret_val)

    def event_market_cycle(self):
        if self.area.current_market is None:
            return
        market_event_channel = f"{self.channel_prefix}/market-events/market"
        current_market_info = self.area.current_market.info
        current_market_info['last_market_stats'] = \
            self.area.stats.get_price_stats_current_market()
        current_market_info["self_sufficiency"] = \
            self.area.endpoint_stats["kpi"].get("self_sufficiency", None)
        current_market_info["market_fee"] = self.area.transfer_fee_const
        data = {"status": "ready",
                "event": "market",
                "market_info": current_market_info}
        self.publish_json(market_event_channel, data)

    def deactivate(self):
        deactivate_event_channel = f"{self.channel_prefix}/events/finish"
        deactivate_msg = {
            "event": "finish"
        }
        self.publish_json(deactivate_event_channel, deactivate_msg)
