import logging
from d3a.d3a_core.redis_connections.redis_area_market_communicator import ResettableCommunicator
from d3a.constants import DISPATCH_EVENT_TICK_FREQUENCY_PERCENT
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


class ExternalMixin:
    def __init__(self, *args, **kwargs):
        self.connected = False
        self._connected = False
        self.redis = ResettableCommunicator()
        super().__init__(*args, **kwargs)
        self._last_dispatched_tick = 0

    @property
    def _dispatch_tick_frequency(self):
        return int(
            self.device.config.ticks_per_slot *
            (DISPATCH_EVENT_TICK_FREQUENCY_PERCENT / 100)
        )

    def _register(self, payload):
        self._connected = register_area(self.redis, self.device.name, self.connected)

    def _unregister(self, payload):
        self._connected = unregister_area(self.redis, self.device.name, self.connected)

    def register_on_market_cycle(self):
        self.connected = self._connected

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

    def _reset_event_tick_counter(self):
        self._last_dispatched_tick = 0

    def _dispatch_event_tick_to_external_agent(self):
        current_tick = self.device.current_tick % self.device.config.ticks_per_slot
        if current_tick - self._last_dispatched_tick >= self._dispatch_tick_frequency:
            tick_event_channel = f"{self.device.name}/tick"
            current_tick_info = {
                "slot_completion":
                    f"{int((current_tick / self.device.config.ticks_per_slot) * 100)}%"
            }
            self._last_dispatched_tick = current_tick
            self.redis.publish_json(tick_event_channel, current_tick_info)
