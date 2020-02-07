import logging
from d3a.d3a_core.redis_connections.redis_area_market_communicator import ResettableCommunicator
from d3a.models.strategy import BaseStrategy
from collections import namedtuple


IncomingRequest = namedtuple('IncomingRequest', ('request_type', 'arguments', 'response_channel'))


def check_for_connected_and_reply(redis, channel_name, is_connected):
    if not is_connected:
        redis.publish_json(
            channel_name, {
                "status": "error",
                "error_message": f"Client should be registered in order to access this area."})
        return False
    return True


def register_area(redis, device_name, is_connected):
    register_response_channel = f'{device_name}/register_participant/response'
    try:
        redis.publish_json(
            register_response_channel,
            {"status": "ready", "registered": True})
        return True
    except Exception as e:
        logging.error(f"Error when registering to area {device_name}: "
                      f"Exception: {str(e)}")
        redis.publish_json(
            register_response_channel,
            {"status": "error",
             "error_message": f"Error when registering to area {device_name}."})
        return is_connected


def unregister_area(redis, device_name, is_connected):
    unregister_response_channel = f'{device_name}/unregister_participant/response'
    if not check_for_connected_and_reply(redis, unregister_response_channel,
                                         is_connected):
        return
    try:
        redis.publish_json(
            unregister_response_channel,
            {"status": "ready", "unregistered": True})
        return False
    except Exception as e:
        logging.error(f"Error when unregistering from area {device_name}: "
                      f"Exception: {str(e)}")
        redis.publish_json(
            unregister_response_channel,
            {"status": "error",
             "error_message": f"Error when unregistering from area {device_name}."})
        return is_connected


class ExternalMixin(BaseStrategy):
    def __init__(self, *args, **kwargs):
        self.connected = False
        self.redis = ResettableCommunicator()
        super().__init__(*args, **kwargs)

    def _register(self, payload):
        self.connected = register_area(self.redis, self.device.name, self.connected)

    def _unregister(self, payload):
        self.connected = unregister_area(self.redis, self.device.name, self.connected)

    def _area_stats(self, payload):
        area_stats_response_channel = f'{self.device.name}/stats/response'
        if not check_for_connected_and_reply(self.redis, area_stats_response_channel,
                                             self.connected):
            return
        try:
            device_stats = {k: v for k, v in self.device.stats.aggregated_stats.items()
                            if v is not None}
            market_stats = {k: v for k, v in self.market_area.stats.aggregated_stats.items()
                            if v is not None}
            self.redis.publish_json(
                area_stats_response_channel,
                {"status": "ready",
                 "device_stats": device_stats,
                 "market_stats": market_stats})
        except Exception as e:
            logging.error(f"Error reporting stats for area {self.device.name}: "
                          f"Exception: {str(e)}")
            self.redis.publish_json(
                area_stats_response_channel,
                {"status": "error",
                 "error_message": f"Error reporting stats for area {self.device.name}."})

    @property
    def market(self):
        return self.market_area.next_market

    @property
    def market_area(self):
        return self.area

    @property
    def device(self):
        return self.owner
